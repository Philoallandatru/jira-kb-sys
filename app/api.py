from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.analysis import analyze_daily_report
from app.cli import _bootstrap
from app.docs import BM25Index
from app.issue_details import build_issue_deep_analysis
from app.management import build_management_summary, write_management_summary_files
from app.models import ManagementSummaryRequest
from app.qa import answer_jira_docs_question, answer_question
from app.reporting import build_daily_report


app = FastAPI(title="Jira Summary API", version="0.3.0")


class ManagementSummaryTaskRequest(BaseModel):
    date_from: str
    date_to: str
    team: str | None = None
    jira_status: list[str] = Field(default_factory=list)
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


def _run_management_summary(run_id: int, request: ManagementSummaryTaskRequest) -> None:
    config, repo = _bootstrap(request.config_path)
    try:
        summary_request = ManagementSummaryRequest(
            date_from=request.date_from,
            date_to=request.date_to,
            team=request.team,
            jira_status=request.jira_status,
        )
        result = build_management_summary(config, repo, summary_request, run_id=run_id)
        repo.save_management_summary(run_id, summary_request, result)
        paths = write_management_summary_files(config, result)
        repo.update_run(run_id, "success", str(paths))
    except Exception as exc:
        repo.update_run(run_id, "failed", str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tasks/reports/management-summary")
def create_management_summary_task(payload: ManagementSummaryTaskRequest, background_tasks: BackgroundTasks) -> dict[str, int | str]:
    _, repo = _bootstrap(payload.config_path)
    run_id = repo.create_run("management-summary", payload.date_to, "queued")
    background_tasks.add_task(_run_management_summary, run_id, payload)
    return {"id": run_id, "status": "queued"}


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
    stale = {key for key in repo.compute_stale_issue_keys(snapshot_date, config.reporting.stale_days) if key in {issue.issue_key for issue in issues}}
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
def get_daily_report(report_date: str, team: str | None = None, jira_status: list[str] = Query(default_factory=list), config_path: str | None = None) -> dict:
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
    result = answer_question(config, BM25Index(repo.load_doc_chunks()), payload.question, top_k=payload.top_k)
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
        BM25Index(repo.load_doc_chunks()),
        payload.question,
        issues,
        issue_analyses,
        daily_analysis,
        top_k=payload.top_k,
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
    with repo.connect() as conn:
        row = conn.execute("SELECT status, details FROM runs WHERE id = ?", (run_id,)).fetchone()
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
