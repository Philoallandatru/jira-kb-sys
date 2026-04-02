from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import shutil

from app.analysis import analyze_daily_report
from app.config import AppConfig, load_config
from app.confluence import ConfluenceCrawler
from app.crawler import JiraCrawler, derive_issue_deltas, iter_snapshot_dates, reconstruct_snapshot_issues
from app.demo import build_demo_chunks, build_demo_issues
from app.docs import DocumentConverter
from app.jira_knowledge import build_jira_chunks, filter_product_doc_chunks
from app.management import build_management_summary, write_management_summary_files
from app.qa import answer_question
from app.retrieval import build_retriever
from app.reporting import build_daily_report, render_markdown, write_report_files
from app.repository import Repository


def _bootstrap(config_path: str | None = None) -> tuple[AppConfig, Repository]:
    config = load_config(config_path)
    repo = Repository(config.storage.database_path)
    return config, repo


def _filter_issues_by_team(issues, team_filter: str | None):
    if not team_filter:
        return issues
    normalized = team_filter.upper()
    return [issue for issue in issues if (issue.team or "").upper() == normalized]


def incremental_sync(config_path: str | None = None) -> None:
    config, repo = _bootstrap(config_path)
    snapshot_date = date.today().isoformat()
    run_id = repo.create_run("incremental-sync", snapshot_date, "running")
    try:
        _crawl_snapshot(config, repo, snapshot_date)
        repo.update_run(run_id, "success", f"Synced snapshot for {snapshot_date}")
        print(f"Incremental sync completed for {snapshot_date}")
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


def full_sync(snapshot_date: str | None = None, config_path: str | None = None) -> None:
    full_sync_range(date_from=snapshot_date, date_to=snapshot_date, config_path=config_path)


def full_sync_range(date_from: str | None = None, date_to: str | None = None, config_path: str | None = None) -> None:
    config, repo = _bootstrap(config_path)
    resolved_from = date_from or date.today().isoformat()
    resolved_to = date_to or resolved_from
    run_id = repo.create_run("full-sync", f"{resolved_from}..{resolved_to}", "running")
    try:
        snapshot_dates = iter_snapshot_dates(resolved_from, resolved_to)
        result = JiraCrawler(config.jira).crawl(resolved_to)
        repo.save_change_events(result.change_events)
        previous_date = repo.get_previous_snapshot_date(resolved_from)
        previous_snapshot: list = repo.load_snapshot(previous_date) if previous_date else []
        for current_date in snapshot_dates:
            snapshot_issues = reconstruct_snapshot_issues(result.issues, result.change_events, current_date)
            deltas = derive_issue_deltas(snapshot_issues, previous_snapshot)
            repo.save_daily_snapshot(current_date, snapshot_issues)
            repo.save_deltas(current_date, deltas)
            previous_snapshot = snapshot_issues
        repo.update_run(run_id, "success", f"Backfilled snapshots for {resolved_from}..{resolved_to}")
        print(f"Full sync completed for {resolved_from}..{resolved_to}")
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


def crawl(config_path: str | None = None) -> None:
    incremental_sync(config_path=config_path)


def _crawl_snapshot(config: AppConfig, repo: Repository, snapshot_date: str) -> None:
    result = JiraCrawler(config.jira).crawl(snapshot_date)
    previous_date = repo.get_previous_snapshot_date(result.snapshot_date)
    previous = repo.load_snapshot(previous_date) if previous_date else []
    deltas = derive_issue_deltas(result.issues, previous)
    repo.save_daily_snapshot(result.snapshot_date, result.issues)
    repo.save_change_events(result.change_events)
    repo.save_deltas(result.snapshot_date, deltas)


def build_docs(config_path: str | None = None) -> None:
    config, repo = _bootstrap(config_path)
    run_id = repo.create_run("build-docs", date.today().isoformat(), "running")
    try:
        converter = DocumentConverter(config.docs)
        confluence_documents = []
        if config.confluence.base_url and config.confluence.space_keys:
            confluence_documents = ConfluenceCrawler(config.confluence, config.docs).crawl_documents()
        _, local_chunks = converter.build_documents()
        confluence_chunks = converter.build_chunks_from_documents(confluence_documents)
        jira_chunks = build_jira_chunks(repo, config.docs)
        all_chunks = local_chunks + confluence_chunks + jira_chunks
        repo.save_doc_chunks(all_chunks)
        build_retriever(config, all_chunks)
        repo.update_run(
            run_id,
            "success",
            (
                f"Indexed {len(all_chunks)} chunks "
                f"({len(local_chunks)} local + {len(confluence_chunks)} confluence + {len(jira_chunks)} jira)"
            ),
        )
        print(
            f"Indexed {len(all_chunks)} chunks "
            f"({len(local_chunks)} local + {len(confluence_chunks)} confluence + {len(jira_chunks)} jira)"
        )
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


def sync_confluence(config_path: str | None = None) -> None:
    config, _ = _bootstrap(config_path)
    crawler = ConfluenceCrawler(config.confluence, config.docs)
    documents = crawler.crawl_documents()
    print(json.dumps({"document_count": len(documents)}, ensure_ascii=False, indent=2))


def report(report_date: str | None = None, config_path: str | None = None) -> None:
    report_date = report_date or date.today().isoformat()
    config, repo = _bootstrap(config_path)
    run_id = repo.create_run("report", report_date, "running")
    try:
        issues = repo.load_snapshot(report_date)
        issues = _filter_issues_by_team(issues, config.reporting.team_filter)
        if not issues:
            raise RuntimeError(f"No snapshot data found for {report_date}")
        issue_keys = {item.issue_key for item in issues}
        deltas = [delta for delta in repo.load_deltas(report_date) if delta.issue_key in issue_keys]
        stale_keys = repo.compute_stale_issue_keys(report_date, config.reporting.stale_days)
        stale_keys = {key for key in stale_keys if key in issue_keys}
        daily_report = build_daily_report(report_date, issues, deltas, stale_keys, config, run_id=run_id)
        daily_analysis = repo.load_daily_analysis(report_date)
        issue_analyses = {
            item.issue_key: item.to_dict()
            for item in repo.load_issue_analyses(report_date)
            if item.issue_key in issue_keys
        }
        markdown_text = render_markdown(daily_report, daily_analysis, issue_analyses)
        paths = write_report_files(config, daily_report, markdown_text, daily_analysis, issue_analyses)
        repo.update_run(run_id, "success", json.dumps(paths, ensure_ascii=False))
        print(json.dumps(paths, ensure_ascii=False, indent=2))
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


def analyze(report_date: str | None = None, config_path: str | None = None) -> None:
    report_date = report_date or date.today().isoformat()
    config, repo = _bootstrap(config_path)
    run_id = repo.create_run("analyze", report_date, "running")
    try:
        issues = repo.load_snapshot(report_date)
        issues = _filter_issues_by_team(issues, config.reporting.team_filter)
        if not issues:
            raise RuntimeError(f"No snapshot data found for {report_date}")
        issue_keys = {item.issue_key for item in issues}
        deltas = [delta for delta in repo.load_deltas(report_date) if delta.issue_key in issue_keys]
        stale_keys = repo.compute_stale_issue_keys(report_date, config.reporting.stale_days)
        stale_keys = {key for key in stale_keys if key in issue_keys}
        report_obj = build_daily_report(report_date, issues, deltas, stale_keys, config)
        chunks = filter_product_doc_chunks(repo.load_doc_chunks())
        daily_analysis, issue_analyses = analyze_daily_report(
            config,
            report_obj,
            build_retriever(config, chunks),
            issues,
            repo=repo,
        )
        repo.save_daily_analysis(daily_analysis)
        repo.save_issue_analyses(issue_analyses)
        repo.update_run(run_id, "success", f"Analyzed {len(issue_analyses)} priority issues")
        print(f"Analyzed {len(issue_analyses)} priority issues")
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


def seed_demo(config_path: str | None = None) -> None:
    config, repo = _bootstrap(config_path)
    run_id = repo.create_run("seed-demo", date.today().isoformat(), "running")
    try:
        demo_issues = build_demo_issues()
        for snapshot_date, issues in demo_issues.items():
            previous_date = repo.get_previous_snapshot_date(snapshot_date)
            previous = repo.load_snapshot(previous_date) if previous_date else []
            repo.save_daily_snapshot(snapshot_date, issues)
            repo.save_deltas(snapshot_date, derive_issue_deltas(issues, previous))
        chunks = build_demo_chunks(config.docs.markdown_dir)
        repo.save_doc_chunks(chunks)
        demo_dir = Path(config.docs.markdown_dir)
        demo_dir.mkdir(parents=True, exist_ok=True)
        for chunk in chunks:
            Path(chunk.source_path).write_text(
                f"# {' / '.join(chunk.section_path)}\n\n{chunk.content}\n",
                encoding="utf-8",
            )
        repo.update_run(run_id, "success", f"Seeded {len(demo_issues)} snapshots and {len(chunks)} chunks")
        print(f"Seeded demo data for dates: {', '.join(sorted(demo_issues.keys()))}")
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


def import_file(source_path: str, config_path: str | None = None) -> None:
    config, _ = _bootstrap(config_path)
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(source_path)
    target = Path(config.docs.raw_dir) / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"Imported {source} -> {target}")


def ask(question: str, config_path: str | None = None, top_k: int = 5) -> None:
    config, repo = _bootstrap(config_path)
    chunks = filter_product_doc_chunks(repo.load_doc_chunks())
    if not chunks:
        raise RuntimeError("No document chunks found. Run `python -m app.cli build-docs` first.")
    result = answer_question(config, build_retriever(config, chunks), question, top_k=top_k, repo=repo)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def management_summary(
    date_from: str,
    date_to: str,
    team: str | None = None,
    jira_status: list[str] | None = None,
    config_path: str | None = None,
) -> None:
    config, repo = _bootstrap(config_path)
    run_id = repo.create_run("management-summary", date_to, "running")
    try:
        from app.models import ManagementSummaryRequest

        request = ManagementSummaryRequest(
            date_from=date_from,
            date_to=date_to,
            team=team,
            jira_status=jira_status or [],
        )
        result = build_management_summary(config, repo, request, run_id=run_id)
        repo.save_management_summary(run_id, request, result)
        paths = write_management_summary_files(config, result)
        repo.update_run(run_id, "success", json.dumps(paths, ensure_ascii=False))
        print(json.dumps({"run_id": run_id, "paths": paths}, ensure_ascii=False, indent=2))
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(prog="jira-summary")
    parser.add_argument("--config", dest="config_path", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("crawl")
    subparsers.add_parser("incremental-sync")
    full_sync_parser = subparsers.add_parser("full-sync")
    full_sync_parser.add_argument("--date", dest="snapshot_date", default=None)
    full_sync_parser.add_argument("--date-from", dest="date_from", default=None)
    full_sync_parser.add_argument("--date-to", dest="date_to", default=None)
    subparsers.add_parser("build-docs")
    subparsers.add_parser("sync-confluence")
    subparsers.add_parser("seed-demo")
    import_parser = subparsers.add_parser("import-file")
    import_parser.add_argument("source_path")
    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--top-k", dest="top_k", type=int, default=5)
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--date", dest="report_date", default=None)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--date", dest="report_date", default=None)
    mgmt_parser = subparsers.add_parser("management-summary")
    mgmt_parser.add_argument("--date-from", required=True, dest="date_from")
    mgmt_parser.add_argument("--date-to", required=True, dest="date_to")
    mgmt_parser.add_argument("--team", default=None)
    mgmt_parser.add_argument("--jira-status", dest="jira_status", action="append", default=[])

    args = parser.parse_args()
    if args.command == "crawl":
        crawl(config_path=args.config_path)
    elif args.command == "incremental-sync":
        incremental_sync(config_path=args.config_path)
    elif args.command == "full-sync":
        if args.date_from or args.date_to:
            full_sync_range(date_from=args.date_from, date_to=args.date_to, config_path=args.config_path)
        else:
            full_sync(snapshot_date=args.snapshot_date, config_path=args.config_path)
    elif args.command == "build-docs":
        build_docs(config_path=args.config_path)
    elif args.command == "sync-confluence":
        sync_confluence(config_path=args.config_path)
    elif args.command == "seed-demo":
        seed_demo(config_path=args.config_path)
    elif args.command == "import-file":
        import_file(args.source_path, config_path=args.config_path)
    elif args.command == "ask":
        ask(args.question, config_path=args.config_path, top_k=args.top_k)
    elif args.command == "report":
        report(report_date=args.report_date, config_path=args.config_path)
    elif args.command == "analyze":
        analyze(report_date=args.report_date, config_path=args.config_path)
    elif args.command == "management-summary":
        management_summary(
            date_from=args.date_from,
            date_to=args.date_to,
            team=args.team,
            jira_status=args.jira_status,
            config_path=args.config_path,
        )


if __name__ == "__main__":
    main()
