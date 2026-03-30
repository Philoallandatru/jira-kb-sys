from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import shutil

from app.analysis import analyze_daily_report
from app.config import AppConfig, load_config
from app.crawler import JiraCrawler, derive_issue_deltas
from app.demo import build_demo_chunks, build_demo_issues
from app.docs import BM25Index, DocumentConverter
from app.models import infer_team_from_issue_key
from app.qa import answer_question
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
    return [issue for issue in issues if (issue.team or infer_team_from_issue_key(issue.issue_key)) == normalized]


def crawl(config_path: str | None = None) -> None:
    config, repo = _bootstrap(config_path)
    snapshot_date = date.today().isoformat()
    run_id = repo.create_run("crawl", snapshot_date, "running")
    try:
        result = JiraCrawler(config.jira).crawl(snapshot_date)
        previous_date = repo.get_previous_snapshot_date(result.snapshot_date)
        previous = repo.load_snapshot(previous_date) if previous_date else []
        deltas = derive_issue_deltas(result.issues, previous)
        repo.save_daily_snapshot(result.snapshot_date, result.issues)
        repo.save_deltas(result.snapshot_date, deltas)
        repo.update_run(run_id, "success", f"Crawled {len(result.issues)} issues")
        print(f"Crawled {len(result.issues)} issues for {result.snapshot_date}")
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


def build_docs(config_path: str | None = None) -> None:
    config, repo = _bootstrap(config_path)
    run_id = repo.create_run("build-docs", date.today().isoformat(), "running")
    try:
        _, chunks = DocumentConverter(config.docs).build_documents()
        repo.save_doc_chunks(chunks)
        repo.update_run(run_id, "success", f"Indexed {len(chunks)} chunks")
        print(f"Indexed {len(chunks)} chunks")
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))
        raise


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
        chunks = repo.load_doc_chunks()
        daily_analysis, issue_analyses = analyze_daily_report(config, report_obj, BM25Index(chunks), issues)
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
            Path(chunk.source_path).write_text(f"# {' / '.join(chunk.section_path)}\n\n{chunk.content}\n", encoding="utf-8")
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
    chunks = repo.load_doc_chunks()
    if not chunks:
        raise RuntimeError("No document chunks found. Run `python -m app.cli build-docs` first.")
    result = answer_question(config, BM25Index(chunks), question, top_k=top_k)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="jira-summary")
    parser.add_argument("--config", dest="config_path", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("crawl")
    subparsers.add_parser("build-docs")
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

    args = parser.parse_args()
    if args.command == "crawl":
        crawl(config_path=args.config_path)
    elif args.command == "build-docs":
        build_docs(config_path=args.config_path)
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


if __name__ == "__main__":
    main()
