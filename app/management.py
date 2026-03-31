from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from requests import RequestException

from app.analysis import LLMClient
from app.config import AppConfig
from app.models import IssueAIAnalysis, IssueChangeEvent, IssueDelta, IssueRecord, ManagementSummaryMetrics, ManagementSummaryRequest, ManagementSummaryResult, utc_now_iso
from app.repository import Repository


def build_management_summary(
    config: AppConfig,
    repo: Repository,
    request: ManagementSummaryRequest,
    run_id: int | None = None,
) -> ManagementSummaryResult:
    snapshot_date = repo.latest_snapshot_on_or_before(request.date_to)
    if not snapshot_date:
        raise RuntimeError(f"No snapshot data found on or before {request.date_to}")
    issues = repo.load_snapshot(snapshot_date)
    change_events = repo.load_change_events_in_range(request.date_from, request.date_to)
    deltas = _events_to_deltas(change_events) or repo.load_deltas_in_range(request.date_from, request.date_to)
    recent_issues = _select_recent_issues(issues, deltas, request)
    issue_keys = [item.issue_key for item in recent_issues]
    metrics = _build_metrics(recent_issues, deltas)
    issue_analyses = {item.issue_key: item for item in repo.load_issue_analyses(snapshot_date)}
    try:
        client = LLMClient(config)
        payload = client.chat_json(
            prompt=json.dumps(
                {
                    "request": request.to_dict(),
                    "metrics": metrics.to_dict(),
                    "recent_issues": [issue.to_dict() for issue in recent_issues[:20]],
                    "recent_deltas": [delta.to_dict() for delta in deltas if delta.issue_key in set(issue_keys)][:50],
                    "recent_change_events": [event.to_dict() for event in change_events if event.issue_key in set(issue_keys)][:50],
                    "issue_analyses": {key: value.to_dict() for key, value in issue_analyses.items() if key in set(issue_keys)},
                },
                ensure_ascii=False,
                indent=2,
            ),
            schema_hint=(
                '{"latest_progress_overview":["string"],'
                '"key_recent_changes":["string"],'
                '"current_risks_and_blockers":["string"],'
                '"root_cause_and_pattern_observations":["string"],'
                '"recommended_management_actions":["string"],'
                '"data_gaps":["string"],'
                '"referenced_issue_keys":["string"],'
                '"referenced_metrics":{"updated_issue_count":0}}'
            ),
            scenario="management_summary",
        )
        return ManagementSummaryResult(
            summary_id=run_id,
            generated_at=utc_now_iso(),
            request=request,
            metrics=metrics,
            latest_progress_overview=_ensure_list(payload.get("latest_progress_overview")),
            key_recent_changes=_ensure_list(payload.get("key_recent_changes")),
            current_risks_and_blockers=_ensure_list(payload.get("current_risks_and_blockers")),
            root_cause_and_pattern_observations=_ensure_list(payload.get("root_cause_and_pattern_observations")),
            recommended_management_actions=_ensure_list(payload.get("recommended_management_actions")),
            data_gaps=_ensure_list(payload.get("data_gaps")),
            referenced_issue_keys=_ensure_list(payload.get("referenced_issue_keys")) or issue_keys[:10],
            referenced_metrics=payload.get("referenced_metrics") if isinstance(payload.get("referenced_metrics"), dict) else _referenced_metrics(metrics),
            raw_response=json.dumps(payload, ensure_ascii=False),
        )
    except (RequestException, ValueError, KeyError):
        return _fallback_management_summary(run_id, request, metrics, recent_issues, deltas, issue_analyses)


def write_management_summary_files(config: AppConfig, result: ManagementSummaryResult) -> dict[str, str]:
    team_slug = (result.request.team or "all").lower()
    status_slug = "-".join(result.request.jira_status).lower() if result.request.jira_status else "all"
    output_dir = Path(config.storage.output_dir) / "management" / f"{result.request.date_from}_to_{result.request.date_to}" / team_slug / status_slug
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "summary.md"
    json_path = output_dir / "summary.json"
    html_path = output_dir / "summary.html"
    pdf_path = output_dir / "summary.pdf"
    markdown_text = render_management_markdown(result)
    md_path.write_text(markdown_text, encoding="utf-8")
    json_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    pdf_written = render_management_pdf(result, html_path, pdf_path)
    paths = {"markdown": str(md_path), "json": str(json_path), "html": str(html_path)}
    if pdf_written:
        paths["pdf"] = str(pdf_path)
    return paths


def render_management_markdown(result: ManagementSummaryResult) -> str:
    lines = [
        f"# Jira 管理层摘要",
        "",
        f"- 时间范围: {result.request.date_from} ~ {result.request.date_to}",
        f"- 团队筛选: {result.request.team or 'All'}",
        f"- 状态筛选: {', '.join(result.request.jira_status) if result.request.jira_status else 'All'}",
        f"- 生成时间: {result.generated_at}",
        "",
        "## 核心指标",
        f"- 最近更新 Jira 数量: {result.metrics.updated_issue_count}",
        f"- 状态推进数量: {result.metrics.status_progress_count}",
        f"- 关闭数量: {result.metrics.closed_count}",
        f"- 重开数量: {result.metrics.reopened_count}",
        f"- 负责人变化数量: {result.metrics.assignee_change_count}",
        f"- 当前阻塞数量: {result.metrics.blocked_count}",
        f"- 当前高优先级未关闭数量: {result.metrics.high_priority_open_count}",
        "",
        "## 最新进展概览",
    ]
    lines.extend([f"- {item}" for item in result.latest_progress_overview])
    lines.extend(["", "## 最近更新中的重点变化"])
    lines.extend([f"- {item}" for item in result.key_recent_changes])
    lines.extend(["", "## 当前风险与阻塞"])
    lines.extend([f"- {item}" for item in result.current_risks_and_blockers])
    lines.extend(["", "## 根因与模式观察"])
    lines.extend([f"- {item}" for item in result.root_cause_and_pattern_observations])
    lines.extend(["", "## 给管理层的建议动作"])
    lines.extend([f"- {item}" for item in result.recommended_management_actions])
    lines.extend(["", "## 数据不足"])
    lines.extend([f"- {item}" for item in result.data_gaps] or ["- 无"])
    return "\n".join(lines) + "\n"


def render_management_pdf(result: ManagementSummaryResult, html_path: Path, pdf_path: Path) -> bool:
    env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")), autoescape=select_autoescape(["html", "xml"]))
    html = env.get_template("management_summary.html").render(result=result.to_dict())
    html_path.write_text(html, encoding="utf-8")
    try:
        from weasyprint import HTML
    except ImportError:
        return False
    HTML(string=html).write_pdf(str(pdf_path))
    return True


def _select_recent_issues(issues: list[IssueRecord], deltas: list[IssueDelta], request: ManagementSummaryRequest) -> list[IssueRecord]:
    issue_map = {issue.issue_key: issue for issue in issues}
    changed_keys = {delta.issue_key for delta in deltas}
    status_filter = {item.lower() for item in request.jira_status}
    selected: list[IssueRecord] = []
    for issue in issues:
        if issue.issue_key not in changed_keys and not _updated_in_range(issue.updated_at, request.date_from, request.date_to):
            continue
        if request.team and (issue.team or "").upper() != request.team.upper():
            continue
        if status_filter and issue.status.lower() not in status_filter:
            continue
        selected.append(issue)
    selected.sort(key=lambda item: item.updated_at or "", reverse=True)
    return selected


def _build_metrics(issues: list[IssueRecord], deltas: list[IssueDelta]) -> ManagementSummaryMetrics:
    issue_keys = {issue.issue_key for issue in issues}
    recent_deltas = [delta for delta in deltas if delta.issue_key in issue_keys]
    assignee_changes = defaultdict(int)
    for delta in recent_deltas:
        if delta.change_type == "assignee_changed":
            assignee_changes[delta.issue_key] += 1
    referenced_issue_keys = [issue.issue_key for issue in issues[:10]]
    team_distribution = Counter((issue.team or "UNKNOWN") for issue in issues)
    status_distribution = Counter(issue.status for issue in issues)
    issues_without_root_cause = 0
    for issue in issues:
        haystack = " ".join([issue.summary or "", issue.description or "", " ".join(issue.comments)])
        if "root cause" not in haystack.lower() and "根因" not in haystack:
            issues_without_root_cause += 1
    return ManagementSummaryMetrics(
        updated_issue_count=len(issues),
        status_progress_count=sum(1 for delta in recent_deltas if delta.change_type == "status_changed"),
        closed_count=sum(1 for delta in recent_deltas if delta.change_type == "closed"),
        reopened_count=sum(1 for delta in recent_deltas if delta.change_type == "reopened"),
        assignee_change_count=sum(1 for delta in recent_deltas if delta.change_type == "assignee_changed"),
        blocked_count=sum(1 for issue in issues if "block" in issue.status.lower()),
        high_priority_open_count=sum(
            1
            for issue in issues
            if (issue.priority or "").lower() in {"highest", "high", "critical", "p0", "p1"}
            and issue.status.lower() not in {"done", "closed", "resolved"}
        ),
        team_distribution=dict(team_distribution),
        status_distribution=dict(status_distribution),
        issues_without_owner=sum(1 for issue in issues if not issue.assignee),
        issues_without_root_cause=issues_without_root_cause,
        referenced_issue_keys=referenced_issue_keys,
    )


def _events_to_deltas(events: list[IssueChangeEvent]) -> list[IssueDelta]:
    deltas: list[IssueDelta] = []
    for event in events:
        if event.change_type not in {"status_changed", "closed", "reopened", "assignee_changed"}:
            continue
        deltas.append(
            IssueDelta(
                issue_key=event.issue_key,
                change_type=event.change_type,
                previous_status=event.from_value if event.field.lower() == "status" else None,
                current_status=event.to_value if event.field.lower() == "status" else None,
                previous_assignee=event.from_value if event.field.lower() == "assignee" else None,
                current_assignee=event.to_value if event.field.lower() == "assignee" else None,
                details=f"{event.field} changed from {event.from_value or '-'} to {event.to_value or '-'}",
            )
        )
    return deltas


def _fallback_management_summary(
    run_id: int | None,
    request: ManagementSummaryRequest,
    metrics: ManagementSummaryMetrics,
    issues: list[IssueRecord],
    deltas: list[IssueDelta],
    issue_analyses: dict[str, IssueAIAnalysis],
) -> ManagementSummaryResult:
    issue_map = {issue.issue_key: issue for issue in issues}
    top_recent = issues[:5]
    latest_progress_overview = [
        f"{metrics.updated_issue_count} 个最近更新的 Jira 进入本次摘要，关闭 {metrics.closed_count} 个，重开 {metrics.reopened_count} 个，当前阻塞 {metrics.blocked_count} 个。"
    ]
    key_recent_changes: list[str] = []
    for delta in deltas:
        issue = issue_map.get(delta.issue_key)
        if not issue:
            continue
        if delta.change_type in {"status_changed", "closed", "reopened", "assignee_changed"}:
            key_recent_changes.append(f"{delta.issue_key}: {delta.details}")
        if len(key_recent_changes) >= 8:
            break
    current_risks_and_blockers = [
        f"{issue.issue_key}: {issue.status} | {issue.summary}"
        for issue in issues
        if "block" in issue.status.lower()
        or ((issue.priority or "").lower() in {"highest", "high", "critical", "p0", "p1"} and issue.status.lower() not in {"done", "closed", "resolved"})
    ][:8]
    root_cause_and_pattern_observations = []
    if metrics.reopened_count:
        root_cause_and_pattern_observations.append(f"时间窗口内有 {metrics.reopened_count} 个重开事件，说明部分问题闭环质量不足。")
    if metrics.assignee_change_count:
        root_cause_and_pattern_observations.append(f"时间窗口内有 {metrics.assignee_change_count} 次负责人变化，协作路径可能存在抖动。")
    if metrics.issues_without_root_cause:
        root_cause_and_pattern_observations.append(f"{metrics.issues_without_root_cause} 个最近更新 Jira 未看到明确根因描述，根因透明度不足。")
    for issue in top_recent:
        analysis = issue_analyses.get(issue.issue_key)
        if analysis and analysis.suspected_root_cause and "insufficient" not in analysis.suspected_root_cause.lower():
            root_cause_and_pattern_observations.append(f"{issue.issue_key}: {analysis.suspected_root_cause}")
            if len(root_cause_and_pattern_observations) >= 6:
                break
    recommended_management_actions = []
    if current_risks_and_blockers:
        recommended_management_actions.append("优先逐条确认阻塞与高优先级未关闭 Jira 的 owner、计划时间和解除条件。")
    if metrics.reopened_count:
        recommended_management_actions.append("针对重开 Jira 做闭环复盘，识别验证不足或发布条件不充分的问题。")
    if metrics.assignee_change_count:
        recommended_management_actions.append("检查负责人频繁切换的 Jira，明确唯一 owner，降低跨团队交接损耗。")
    if metrics.issues_without_root_cause:
        recommended_management_actions.append("要求高风险 Jira 补齐根因字段或等价说明，避免管理层只能看到现象。")
    data_gaps = []
    if metrics.issues_without_owner:
        data_gaps.append(f"{metrics.issues_without_owner} 个最近更新 Jira 缺少负责人，协作效率判断不完整。")
    if metrics.issues_without_root_cause:
        data_gaps.append(f"{metrics.issues_without_root_cause} 个最近更新 Jira 缺少明确根因描述。")
    if not deltas:
        data_gaps.append("当前时间范围内没有抓到变更事件，重点变化判断依赖 updated_at。")
    return ManagementSummaryResult(
        summary_id=run_id,
        generated_at=utc_now_iso(),
        request=request,
        metrics=metrics,
        latest_progress_overview=latest_progress_overview,
        key_recent_changes=key_recent_changes or ["当前时间范围内未发现显著状态推进、关闭、重开或负责人变化。"],
        current_risks_and_blockers=current_risks_and_blockers or ["未发现明确阻塞，但仍需关注高优先级未关闭项。"],
        root_cause_and_pattern_observations=root_cause_and_pattern_observations or ["当前数据不足以形成稳定的根因模式判断。"],
        recommended_management_actions=recommended_management_actions or ["继续观察最近更新 Jira，并补充根因与责任人信息。"],
        data_gaps=data_gaps,
        referenced_issue_keys=metrics.referenced_issue_keys,
        referenced_metrics=_referenced_metrics(metrics),
        raw_response="offline-fallback",
    )


def _updated_in_range(updated_at: str | None, date_from: str, date_to: str) -> bool:
    if not updated_at:
        return False
    try:
        updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return date_from <= updated.isoformat() <= date_to


def _referenced_metrics(metrics: ManagementSummaryMetrics) -> dict[str, int | float | str]:
    return {
        "updated_issue_count": metrics.updated_issue_count,
        "status_progress_count": metrics.status_progress_count,
        "closed_count": metrics.closed_count,
        "reopened_count": metrics.reopened_count,
        "assignee_change_count": metrics.assignee_change_count,
        "blocked_count": metrics.blocked_count,
        "high_priority_open_count": metrics.high_priority_open_count,
        "issues_without_owner": metrics.issues_without_owner,
        "issues_without_root_cause": metrics.issues_without_root_cause,
    }


def _ensure_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]
