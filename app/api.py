from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from app.analysis import analyze_daily_report
from app.cli import _bootstrap
from app.confluence import ConfluenceCrawler, ConfluenceError
from app.crawler import CrawlerError, JiraCrawler
from app.docs import DocumentConverter
from app.issue_details import build_issue_deep_analysis
from app.jira_knowledge import build_jira_chunks, filter_jira_doc_chunks, filter_product_doc_chunks
from app.management import build_management_summary, write_management_summary_files
from app.models import ManagementSummaryRequest
from app.qa import answer_jira_docs_question, answer_question
from app.retrieval import build_retriever
from app.reporting import build_daily_report, render_markdown, write_report_files


TASK_POLL_INTERVAL_SECONDS = 1.0
TASK_MAX_ATTEMPTS = 3
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_RUN_CANCEL_EVENTS: dict[int, threading.Event] = {}
_RUN_CANCEL_LOCK = threading.Lock()


class TaskCancelledError(RuntimeError):
    pass


def _register_run_cancel_event(run_id: int) -> threading.Event:
    event = threading.Event()
    with _RUN_CANCEL_LOCK:
        _RUN_CANCEL_EVENTS[run_id] = event
    return event


def _unregister_run_cancel_event(run_id: int) -> None:
    with _RUN_CANCEL_LOCK:
        _RUN_CANCEL_EVENTS.pop(run_id, None)


def _signal_run_cancel(run_id: int) -> bool:
    with _RUN_CANCEL_LOCK:
        event = _RUN_CANCEL_EVENTS.get(run_id)
    if not event:
        return False
    event.set()
    return True


def _raise_if_cancelled(cancel_event: threading.Event | None, run_id: int) -> None:
    if cancel_event and cancel_event.is_set():
        raise TaskCancelledError(f"Task #{run_id} was cancelled")


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop_event = threading.Event()
    worker = threading.Thread(target=_task_worker_loop, args=(stop_event,), name="jira-summary-worker", daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop_event.set()
        worker.join(timeout=5)


app = FastAPI(title="Jira Summary API", version="0.5.0", lifespan=lifespan)
_app_config, _ = _bootstrap(None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_app_config.server.cors_allow_origins,
    allow_origin_regex=_app_config.server.cors_allow_origin_regex,
    allow_credentials=_app_config.server.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ManagementSummaryTaskRequest(BaseModel):
    date_from: str
    date_to: str
    team: str | None = None
    jira_status: list[str] = Field(default_factory=list)
    config_path: str | None = None


class SimpleTaskRequest(BaseModel):
    config_path: str | None = None


class DailyTaskRequest(BaseModel):
    report_date: str | None = None
    config_path: str | None = None


class SyncTaskRequest(BaseModel):
    snapshot_date: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    config_path: str | None = None


class PromptSettingsPayload(BaseModel):
    default_language: str | None = None
    max_output_tokens: int | None = Field(default=None, ge=256)
    scenario_max_output_tokens: dict[str, int] | None = None
    custom_prompts: dict[str, str] | None = None


class DocsQuestionPayload(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)
    config_path: str | None = None


class JiraDocsQuestionPayload(DocsQuestionPayload):
    snapshot_date: str | None = None


class JiraConnectionResponse(BaseModel):
    ok: bool
    base_url: str
    server_title: str | None = None
    version: str | None = None
    deployment_type: str | None = None
    authenticated_user: str | None = None
    project_filter_count: int
    has_jql: bool


class ConfluenceConnectionResponse(BaseModel):
    ok: bool
    base_url: str
    authenticated_user: str | None = None
    crawl_mode: str
    space_keys: list[str]
    sample_spaces: list[str] = Field(default_factory=list)


class UploadDocsResponse(BaseModel):
    saved_files: list[str]
    destination_dir: str
    supported_extensions: list[str]
    message: str


def _run_management_summary(
    run_id: int,
    request: ManagementSummaryTaskRequest,
    cancel_event: threading.Event | None = None,
) -> None:
    _raise_if_cancelled(cancel_event, run_id)
    config, repo = _bootstrap(request.config_path)
    summary_request = ManagementSummaryRequest(
        date_from=request.date_from,
        date_to=request.date_to,
        team=request.team,
        jira_status=request.jira_status,
    )
    result = build_management_summary(config, repo, summary_request, run_id=run_id)
    _raise_if_cancelled(cancel_event, run_id)
    repo.save_management_summary(run_id, summary_request, result)
    paths = write_management_summary_files(config, result)
    repo.update_run(run_id, "success", str(paths))


def _run_incremental_sync(run_id: int, request: SyncTaskRequest, cancel_event: threading.Event | None = None) -> None:
    _raise_if_cancelled(cancel_event, run_id)
    config, repo = _bootstrap(request.config_path)
    snapshot_date = request.snapshot_date or date.today().isoformat()
    _crawl_snapshot(config, repo, snapshot_date, cancel_event=cancel_event, run_id=run_id)
    repo.update_run(run_id, "success", f"Synced snapshot for {snapshot_date}")


def _run_full_sync(run_id: int, request: SyncTaskRequest, cancel_event: threading.Event | None = None) -> None:
    _raise_if_cancelled(cancel_event, run_id)
    config, repo = _bootstrap(request.config_path)
    from app.crawler import JiraCrawler, derive_issue_deltas, iter_snapshot_dates, reconstruct_snapshot_issues

    resolved_from = request.date_from or request.snapshot_date or date.today().isoformat()
    resolved_to = request.date_to or request.snapshot_date or resolved_from
    snapshot_dates = iter_snapshot_dates(resolved_from, resolved_to)
    result = JiraCrawler(config.jira).crawl(resolved_to)
    repo.save_change_events(result.change_events)
    previous_date = repo.get_previous_snapshot_date(resolved_from)
    previous_snapshot: list = repo.load_snapshot(previous_date) if previous_date else []
    for current_date in snapshot_dates:
        _raise_if_cancelled(cancel_event, run_id)
        snapshot_issues = reconstruct_snapshot_issues(result.issues, result.change_events, current_date)
        deltas = derive_issue_deltas(snapshot_issues, previous_snapshot)
        repo.save_daily_snapshot(current_date, snapshot_issues)
        repo.save_deltas(current_date, deltas)
        previous_snapshot = snapshot_issues
    repo.update_run(run_id, "success", f"Backfilled snapshots for {resolved_from}..{resolved_to}")


def _crawl_snapshot(
    config,
    repo,
    snapshot_date: str,
    cancel_event: threading.Event | None = None,
    run_id: int | None = None,
) -> None:
    if run_id is not None:
        _raise_if_cancelled(cancel_event, run_id)
    from app.crawler import JiraCrawler, derive_issue_deltas

    result = JiraCrawler(config.jira).crawl(snapshot_date)
    if run_id is not None:
        _raise_if_cancelled(cancel_event, run_id)
    previous_date = repo.get_previous_snapshot_date(result.snapshot_date)
    previous = repo.load_snapshot(previous_date) if previous_date else []
    deltas = derive_issue_deltas(result.issues, previous)
    repo.save_daily_snapshot(result.snapshot_date, result.issues)
    repo.save_change_events(result.change_events)
    repo.save_deltas(result.snapshot_date, deltas)


def _run_crawl(run_id: int, request: SimpleTaskRequest, cancel_event: threading.Event | None = None) -> None:
    _run_incremental_sync(run_id, SyncTaskRequest(config_path=request.config_path), cancel_event=cancel_event)


def _run_build_docs(run_id: int, request: SimpleTaskRequest, cancel_event: threading.Event | None = None) -> None:
    _raise_if_cancelled(cancel_event, run_id)
    config, repo = _bootstrap(request.config_path)
    converter = DocumentConverter(config.docs)
    confluence_documents = []
    if config.confluence.base_url and config.confluence.space_keys:
        confluence_documents = ConfluenceCrawler(config.confluence, config.docs).crawl_documents()
    _raise_if_cancelled(cancel_event, run_id)
    _, product_chunks = converter.build_documents()
    confluence_chunks = converter.build_chunks_from_documents(confluence_documents)
    jira_chunks = build_jira_chunks(repo, config.docs)
    all_chunks = product_chunks + confluence_chunks + jira_chunks
    repo.save_doc_chunks(all_chunks)
    build_retriever(config, all_chunks)
    repo.update_run(
        run_id,
        "success",
        (
            f"Indexed {len(all_chunks)} chunks "
            f"({len(product_chunks)} local + {len(confluence_chunks)} confluence + {len(jira_chunks)} jira)"
        ),
    )


def _run_confluence_sync(run_id: int, request: SimpleTaskRequest, cancel_event: threading.Event | None = None) -> None:
    _raise_if_cancelled(cancel_event, run_id)
    config, repo = _bootstrap(request.config_path)
    documents = ConfluenceCrawler(config.confluence, config.docs).crawl_documents()
    _raise_if_cancelled(cancel_event, run_id)
    repo.update_run(run_id, "success", f"Fetched {len(documents)} Confluence pages")


def _run_analyze(run_id: int, request: DailyTaskRequest, cancel_event: threading.Event | None = None) -> None:
    _raise_if_cancelled(cancel_event, run_id)
    config, repo = _bootstrap(request.config_path)
    report_date = request.report_date or date.today().isoformat()
    issues = repo.load_snapshot(report_date)
    issues = _filter_issues(issues, config.reporting.team_filter, [])
    if not issues:
        raise RuntimeError(f"No snapshot data found for {report_date}")
    issue_keys = {item.issue_key for item in issues}
    deltas = [delta for delta in repo.load_deltas(report_date) if delta.issue_key in issue_keys]
    stale_keys = repo.compute_stale_issue_keys(report_date, config.reporting.stale_days)
    stale_keys = {key for key in stale_keys if key in issue_keys}
    report_obj = build_daily_report(report_date, issues, deltas, stale_keys, config, run_id=run_id)
    chunks = filter_product_doc_chunks(repo.load_doc_chunks())
    _raise_if_cancelled(cancel_event, run_id)
    daily_analysis, issue_analyses = analyze_daily_report(config, report_obj, build_retriever(config, chunks), issues)
    _raise_if_cancelled(cancel_event, run_id)
    repo.save_daily_analysis(daily_analysis)
    repo.save_issue_analyses(issue_analyses)
    repo.update_run(run_id, "success", f"Analyzed {len(issue_analyses)} priority issues for {report_date}")


def _run_daily_report(run_id: int, request: DailyTaskRequest, cancel_event: threading.Event | None = None) -> None:
    _raise_if_cancelled(cancel_event, run_id)
    config, repo = _bootstrap(request.config_path)
    report_date = request.report_date or date.today().isoformat()
    issues = repo.load_snapshot(report_date)
    issues = _filter_issues(issues, config.reporting.team_filter, [])
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
    _raise_if_cancelled(cancel_event, run_id)
    markdown_text = render_markdown(daily_report, daily_analysis, issue_analyses)
    paths = write_report_files(config, daily_report, markdown_text, daily_analysis, issue_analyses)
    repo.update_run(run_id, "success", json.dumps(paths, ensure_ascii=False))


def _task_worker_loop(stop_event: threading.Event) -> None:
    recovered_inflight = False
    while not stop_event.is_set():
        try:
            _, repo = _bootstrap(None)
            if not recovered_inflight:
                repo.requeue_running_runs("Recovered interrupted in-process task after service restart")
                recovered_inflight = True
            row = repo.claim_next_queued_run()
            if not row:
                stop_event.wait(TASK_POLL_INTERVAL_SECONDS)
                continue
            _execute_queued_run(int(row["id"]), str(row["run_type"]), row.get("payload_json"), repo)
        except Exception:
            stop_event.wait(TASK_POLL_INTERVAL_SECONDS)


def _execute_queued_run(run_id: int, run_type: str, payload_json: str | None, repo) -> None:
    task_map = {
        "management-summary": (ManagementSummaryTaskRequest, _run_management_summary),
        "incremental-sync": (SyncTaskRequest, _run_incremental_sync),
        "full-sync": (SyncTaskRequest, _run_full_sync),
        "confluence-sync": (SimpleTaskRequest, _run_confluence_sync),
        "crawl": (SimpleTaskRequest, _run_crawl),
        "build-docs": (SimpleTaskRequest, _run_build_docs),
        "analyze": (DailyTaskRequest, _run_analyze),
        "report": (DailyTaskRequest, _run_daily_report),
    }
    model_and_handler = task_map.get(run_type)
    if not model_and_handler:
        repo.update_run(run_id, "failed", f"Unknown task type: {run_type}")
        return
    model_cls, handler = model_and_handler
    cancel_event = _register_run_cancel_event(run_id)
    try:
        payload = model_cls.model_validate(json.loads(payload_json) if payload_json else {})
        _raise_if_cancelled(cancel_event, run_id)
        handler(run_id, payload, cancel_event)
    except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
        repo.update_run(run_id, "failed", f"Invalid task payload: {exc}")
    except TaskCancelledError as exc:
        repo.update_run(run_id, "cancelled", str(exc))
    except Exception as exc:
        repo.schedule_retry(run_id, str(exc), TASK_MAX_ATTEMPTS)
    finally:
        _unregister_run_cancel_event(run_id)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/integrations/jira/health")
def get_jira_connection_health(config_path: str | None = None) -> dict[str, object]:
    config, _ = _bootstrap(config_path)
    try:
        return JiraConnectionResponse.model_validate(JiraCrawler(config.jira).check_connection()).model_dump()
    except CrawlerError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "base_url": config.jira.base_url,
                "message": str(exc),
            },
        ) from exc


@app.get("/integrations/confluence/health")
def get_confluence_connection_health(config_path: str | None = None) -> dict[str, object]:
    config, _ = _bootstrap(config_path)
    try:
        return ConfluenceConnectionResponse.model_validate(
            ConfluenceCrawler(config.confluence, config.docs).check_connection()
        ).model_dump()
    except ConfluenceError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "base_url": config.confluence.base_url,
                "message": str(exc),
            },
        ) from exc


@app.post("/tasks/reports/management-summary")
def create_management_summary_task(
    payload: ManagementSummaryTaskRequest,
) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    run_id = repo.create_run("management-summary", payload.date_to, "queued", payload=payload.model_dump())
    return {"id": run_id, "status": "queued"}


@app.post("/tasks/sync/incremental")
def create_incremental_sync_task(
    payload: SyncTaskRequest,
) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    snapshot_date = payload.snapshot_date or date.today().isoformat()
    run_id = repo.create_run("incremental-sync", snapshot_date, "queued", payload=payload.model_dump())
    return {"id": run_id, "status": "queued"}


@app.post("/tasks/sync/full")
def create_full_sync_task(
    payload: SyncTaskRequest,
) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    run_label = payload.snapshot_date or f"{payload.date_from or date.today().isoformat()}..{payload.date_to or payload.date_from or date.today().isoformat()}"
    run_id = repo.create_run("full-sync", run_label, "queued", payload=payload.model_dump())
    return {"id": run_id, "status": "queued"}


@app.post("/tasks/crawl")
def create_crawl_task(payload: SimpleTaskRequest) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    snapshot_date = date.today().isoformat()
    run_id = repo.create_run("crawl", snapshot_date, "queued", payload=payload.model_dump())
    return {"id": run_id, "status": "queued"}


@app.post("/tasks/sync/confluence")
def create_confluence_sync_task(payload: SimpleTaskRequest) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    run_id = repo.create_run("confluence-sync", date.today().isoformat(), "queued", payload=payload.model_dump())
    return {"id": run_id, "status": "queued"}


@app.post("/tasks/build-docs")
def create_build_docs_task(payload: SimpleTaskRequest) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    run_id = repo.create_run("build-docs", date.today().isoformat(), "queued", payload=payload.model_dump())
    return {"id": run_id, "status": "queued"}


@app.post("/docs/upload")
async def upload_raw_docs(
    files: list[UploadFile] = File(...),
    config_path: str | None = None,
) -> dict[str, object]:
    config = _load_config_only(config_path)
    if not files:
        raise HTTPException(status_code=400, detail="未提供上传文件")

    raw_dir = Path(config.docs.raw_dir)
    supported_extensions = {item.lower() for item in config.docs.supported_extensions}
    seen_names: set[str] = set()
    pending_writes: list[tuple[Path, bytes]] = []
    errors: list[str] = []

    for upload in files:
        filename = Path(upload.filename or "").name
        if not filename:
            errors.append("存在缺少文件名的上传项")
            continue
        if filename in seen_names:
            errors.append(f"上传请求中存在重复文件名: {filename}")
            continue
        seen_names.add(filename)

        suffix = Path(filename).suffix.lower()
        if suffix not in supported_extensions:
            errors.append(f"文件格式不支持: {filename}，仅支持 {', '.join(sorted(supported_extensions))}")
            continue

        target = raw_dir / filename
        if target.exists():
            errors.append(f"文件已存在，请先重命名后再上传: {filename}")
            continue

        content = await upload.read()
        if not content:
            errors.append(f"文件内容为空: {filename}")
            continue
        if len(content) > MAX_UPLOAD_BYTES:
            errors.append(f"文件过大，超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MB 限制: {filename}")
            continue

        pending_writes.append((target, content))

    if errors:
        raise HTTPException(status_code=400, detail={"message": "文档上传校验失败", "errors": errors})

    raw_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []
    for target, content in pending_writes:
        target.write_bytes(content)
        saved_files.append(str(target.resolve()))

    return UploadDocsResponse(
        saved_files=saved_files,
        destination_dir=str(raw_dir.resolve()),
        supported_extensions=sorted(supported_extensions),
        message="文件已保存，请手动执行“构建文档索引”以纳入知识库。",
    ).model_dump()


@app.post("/tasks/analyze")
def create_analyze_task(payload: DailyTaskRequest) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    report_date = payload.report_date or date.today().isoformat()
    run_id = repo.create_run("analyze", report_date, "queued", payload=payload.model_dump())
    return {"id": run_id, "status": "queued"}


@app.post("/tasks/report")
def create_report_task(payload: DailyTaskRequest) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    report_date = payload.report_date or date.today().isoformat()
    run_id = repo.create_run("report", report_date, "queued", payload=payload.model_dump())
    return {"id": run_id, "status": "queued"}


@app.get("/tasks")
def list_tasks(limit: int = Query(default=50, ge=1, le=200), config_path: str | None = None) -> dict:
    _, repo = _bootstrap(config_path)
    return {"items": [_serialize_run(row) for row in repo.list_runs(limit=limit)]}


@app.get("/tasks/{run_id}")
def get_task(run_id: int, config_path: str | None = None) -> dict:
    _, repo = _bootstrap(config_path)
    row = repo.load_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return _serialize_run(row)


@app.post("/tasks/{run_id}/cancel")
def cancel_task(run_id: int, config_path: str | None = None) -> dict[str, int | str]:
    _, repo = _bootstrap(config_path)
    state = repo.cancel_run(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    if state == "cancelling":
        _signal_run_cancel(run_id)
        row = repo.load_run(run_id)
        return {"id": run_id, "status": str(row["status"]) if row else "running", "message": "Cancellation requested"}
    row = repo.load_run(run_id)
    return {
        "id": run_id,
        "status": str(row["status"]) if row else state,
        "message": "Task cancelled" if state == "cancelled" else f"Task already {state}",
    }


@app.get("/reports/management-summary/{run_id}")
def get_management_summary(run_id: int, config_path: str | None = None) -> dict:
    _, repo = _bootstrap(config_path)
    result = repo.load_management_summary(run_id)
    if result:
        return {"id": run_id, "status": "success", "result": result.to_dict()}
    row = _load_run(repo, run_id)
    return {"id": run_id, "status": row["status"], "details": row["details"]}


@app.get("/dashboard/overview")
def get_dashboard_overview(
    report_date: str | None = None,
    team: str | None = None,
    jira_status: list[str] = Query(default_factory=list),
    config_path: str | None = None,
) -> dict:
    config, repo = _bootstrap(config_path)
    snapshot_date = _resolve_snapshot_date(repo, report_date)
    issues = _filter_issues(repo.load_snapshot(snapshot_date), team, jira_status)
    deltas = [delta for delta in repo.load_deltas(snapshot_date) if delta.issue_key in {issue.issue_key for issue in issues}]
    stale = {
        key for key in repo.compute_stale_issue_keys(snapshot_date, config.reporting.stale_days)
        if key in {issue.issue_key for issue in issues}
    }
    report = build_daily_report(snapshot_date, issues, deltas, stale, config)
    daily_analysis = repo.load_daily_analysis(snapshot_date)
    return {
        "snapshot_date": snapshot_date,
        "metrics": report.metrics.to_dict(),
        "project_summaries": [item.to_dict() for item in report.project_summaries],
        "priority_issues": [item.to_dict() for item in report.priority_issues[:8]],
        "daily_analysis": daily_analysis.to_dict() if daily_analysis else None,
    }


@app.get("/reports/daily")
def list_daily_reports(limit: int = Query(default=14, ge=1, le=90), config_path: str | None = None) -> dict:
    _, repo = _bootstrap(config_path)
    dates = repo.list_snapshot_dates()[:limit]
    rows = []
    for snapshot_date in dates:
        issues = repo.load_snapshot(snapshot_date)
        daily_analysis = repo.load_daily_analysis(snapshot_date)
        rows.append(
            {
                "report_date": snapshot_date,
                "issue_count": len(issues),
                "blocked_count": sum(1 for issue in issues if "block" in issue.status.lower()),
                "high_priority_open_count": sum(
                    1
                    for issue in issues
                    if (issue.priority or "").lower() in {"highest", "high", "critical", "p0", "p1"}
                    and issue.status.lower() not in {"done", "closed", "resolved"}
                ),
                "overall_health": daily_analysis.overall_health if daily_analysis else None,
            }
        )
    return {"items": rows}


@app.get("/reports/daily/{report_date}")
def get_daily_report(
    report_date: str,
    team: str | None = None,
    jira_status: list[str] = Query(default_factory=list),
    config_path: str | None = None,
) -> dict:
    config, repo = _bootstrap(config_path)
    snapshot_date = _resolve_snapshot_date(repo, report_date)
    issues = _filter_issues(repo.load_snapshot(snapshot_date), team, jira_status)
    issue_keys = {issue.issue_key for issue in issues}
    deltas = [delta for delta in repo.load_deltas(snapshot_date) if delta.issue_key in issue_keys]
    stale = {key for key in repo.compute_stale_issue_keys(snapshot_date, config.reporting.stale_days) if key in issue_keys}
    report = build_daily_report(snapshot_date, issues, deltas, stale, config)
    daily_analysis = repo.load_daily_analysis(snapshot_date)
    issue_analyses = [item.to_dict() for item in repo.load_issue_analyses(snapshot_date) if item.issue_key in issue_keys]
    return {
        "report": report.to_dict(),
        "daily_analysis": daily_analysis.to_dict() if daily_analysis else None,
        "issue_analyses": issue_analyses,
    }


@app.get("/issues")
def list_issues(
    report_date: str | None = None,
    team: str | None = None,
    jira_status: list[str] = Query(default_factory=list),
    query: str | None = None,
    config_path: str | None = None,
) -> dict:
    _, repo = _bootstrap(config_path)
    snapshot_date = _resolve_snapshot_date(repo, report_date)
    issues = _filter_issues(repo.load_snapshot(snapshot_date), team, jira_status)
    if query:
        query_lower = query.lower()
        issues = [
            issue
            for issue in issues
            if query_lower in issue.issue_key.lower()
            or query_lower in issue.summary.lower()
            or query_lower in (issue.description or "").lower()
        ]
    return {"snapshot_date": snapshot_date, "items": [issue.to_dict() for issue in issues]}


@app.get("/issues/{issue_key}")
def get_issue_detail(issue_key: str, report_date: str | None = None, config_path: str | None = None) -> dict:
    _, repo = _bootstrap(config_path)
    snapshot_date = _resolve_snapshot_date(repo, report_date)
    issue = repo.load_issue(issue_key, snapshot_date)
    if not issue:
        raise HTTPException(status_code=404, detail=f"issue `{issue_key}` not found")
    issue_analysis = next((item for item in repo.load_issue_analyses(snapshot_date) if item.issue_key == issue_key), None)
    deltas = [delta.to_dict() for delta in repo.load_deltas(snapshot_date) if delta.issue_key == issue_key]
    return {
        "snapshot_date": snapshot_date,
        "issue": issue.to_dict(),
        "issue_analysis": issue_analysis.to_dict() if issue_analysis else None,
        "deltas": deltas,
    }


@app.get("/issues/{issue_key}/deep-analysis")
def get_issue_deep_analysis(issue_key: str, report_date: str | None = None, config_path: str | None = None) -> dict:
    config, repo = _bootstrap(config_path)
    snapshot_date = _resolve_snapshot_date(repo, report_date)
    result = build_issue_deep_analysis(config, repo, issue_key, snapshot_date=snapshot_date)
    return {"snapshot_date": snapshot_date, "result": result.to_dict()}


@app.post("/qa/docs")
def post_docs_qa(payload: DocsQuestionPayload) -> dict:
    config, repo = _bootstrap(payload.config_path)
    result = answer_question(
        config,
        build_retriever(config, filter_product_doc_chunks(repo.load_doc_chunks())),
        payload.question,
        top_k=payload.top_k,
        repo=repo,
    )
    return result.to_dict()


@app.post("/qa/jira-docs")
def post_jira_docs_qa(payload: JiraDocsQuestionPayload) -> dict:
    config, repo = _bootstrap(payload.config_path)
    snapshot_date = _resolve_snapshot_date(repo, payload.snapshot_date)
    issues = repo.load_snapshot(snapshot_date)
    issue_analyses = repo.load_issue_analyses(snapshot_date)
    daily_analysis = repo.load_daily_analysis(snapshot_date)
    result = answer_jira_docs_question(
        config,
        build_retriever(config, repo.load_doc_chunks()),
        None,
        payload.question,
        issues,
        issue_analyses,
        daily_analysis,
        top_k=payload.top_k,
        repo=repo,
    )
    return {"snapshot_date": snapshot_date, **result.to_dict()}


@app.get("/settings/prompts")
def get_prompt_settings(config_path: str | None = None) -> dict:
    config = _load_config_only(config_path)
    return {
        "default_language": config.llm.default_language,
        "max_output_tokens": config.llm.max_output_tokens,
        "scenario_max_output_tokens": config.llm.scenario_max_output_tokens,
        "custom_prompts": config.llm.custom_prompts,
    }


@app.put("/settings/prompts")
def update_prompt_settings(payload: PromptSettingsPayload, config_path: str | None = None) -> dict:
    resolved = Path(config_path or "./config.yaml")
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    llm = data.setdefault("llm", {})
    if payload.default_language is not None:
        llm["default_language"] = payload.default_language
    if payload.max_output_tokens is not None:
        llm["max_output_tokens"] = payload.max_output_tokens
    if payload.scenario_max_output_tokens is not None:
        llm["scenario_max_output_tokens"] = payload.scenario_max_output_tokens
    if payload.custom_prompts is not None:
        llm["custom_prompts"] = payload.custom_prompts
    resolved.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return get_prompt_settings(str(resolved))


def _load_run(repo, run_id: int):
    row = repo.load_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return row


def _resolve_snapshot_date(repo, requested_date: str | None) -> str:
    if requested_date:
        snapshot_date = repo.latest_snapshot_on_or_before(requested_date)
    else:
        snapshot_date = repo.latest_snapshot_date()
    if not snapshot_date:
        raise HTTPException(status_code=404, detail="no snapshot data found")
    return snapshot_date


def _filter_issues(issues, team: str | None, jira_status: list[str]):
    status_filter = {item.lower() for item in jira_status}
    filtered = []
    for issue in issues:
        if team and (issue.team or "").upper() != team.upper():
            continue
        if status_filter and issue.status.lower() not in status_filter:
            continue
        filtered.append(issue)
    return filtered


def _load_config_only(config_path: str | None = None):
    config, _ = _bootstrap(config_path)
    return config


def _serialize_run(row: dict) -> dict:
    details = row.get("details")
    parsed_details = None
    if isinstance(details, str) and details:
        try:
            parsed_details = json.loads(details)
        except json.JSONDecodeError:
            parsed_details = None
    return {
        "id": row["id"],
        "run_type": row["run_type"],
        "run_date": row["run_date"],
        "status": row["status"],
        "can_cancel": row["status"] in {"queued", "running"},
        "details": details,
        "details_json": parsed_details,
        "attempt_count": row.get("attempt_count", 0),
        "last_error": row.get("last_error"),
        "created_at": row["created_at"],
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
    }


def main() -> None:
    import uvicorn

    config = _load_config_only()
    uvicorn.run("app.api:app", host=config.server.host, port=config.server.port, reload=False)


if __name__ == "__main__":
    main()
