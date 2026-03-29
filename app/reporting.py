from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import AppConfig
from app.models import DailyAIAnalysis, DailyMetrics, DailyReport, IssueDelta, IssueRecord, PriorityIssue, ProjectSummary, utc_now_iso


def build_daily_report(report_date: str, issues: list[IssueRecord], deltas: list[IssueDelta], stale_issue_keys: set[str], config: AppConfig, run_id: int | None = None) -> DailyReport:
    delta_map = defaultdict(list)
    for delta in deltas:
        delta_map[delta.issue_key].append(delta.details)

    risk_keywords = [item.lower() for item in config.reporting.risk_keywords]
    priority_issues: list[PriorityIssue] = []
    for issue in issues:
        text = " ".join([issue.summary, issue.status, " ".join(issue.labels), " ".join(issue.components)]).lower()
        should_include = (
            (issue.priority or "").lower() in {"highest", "high", "critical", "p0", "p1"}
            or issue.issue_key in stale_issue_keys
            or any(keyword in text for keyword in risk_keywords)
            or issue.issue_key in delta_map
        )
        if should_include:
            priority_issues.append(
                PriorityIssue(
                    issue_key=issue.issue_key,
                    summary=issue.summary,
                    status=issue.status,
                    assignee=issue.assignee,
                    priority=issue.priority,
                    change_summary="; ".join(delta_map.get(issue.issue_key, ["No major change detected"])),
                )
            )
    priority_issues = priority_issues[: config.reporting.top_issue_limit]
    return DailyReport(
        report_date=report_date,
        generated_at=utc_now_iso(),
        run_id=run_id,
        metrics=DailyMetrics.from_issues(issues, deltas, stale_issue_keys),
        project_summaries=_project_summaries(issues),
        priority_issues=priority_issues,
    )


def _project_summaries(issues: list[IssueRecord]) -> list[ProjectSummary]:
    grouped: dict[str, list[IssueRecord]] = defaultdict(list)
    for issue in issues:
        grouped[issue.project or "UNKNOWN"].append(issue)
    rows: list[ProjectSummary] = []
    for project, items in sorted(grouped.items()):
        closed = sum(1 for issue in items if issue.status.lower() in {"done", "closed", "resolved"})
        blocked = sum(1 for issue in items if "block" in issue.status.lower())
        rows.append(ProjectSummary(project=project, total=len(items), open_count=len(items) - closed, closed_count=closed, blocked_count=blocked))
    return rows


def render_markdown(report: DailyReport, daily_analysis: DailyAIAnalysis | None = None, issue_analyses: dict[str, dict] | None = None) -> str:
    lines = [
        f"# Jira Daily Report - {report.report_date}",
        "",
        f"- Generated at: {report.generated_at}",
        f"- Source run: {report.run_id or 'n/a'}",
        "",
        "## Overview",
        f"- Total issues: {report.metrics.total_issues}",
        f"- New issues: {report.metrics.new_issues}",
        f"- Closed issues: {report.metrics.closed_issues}",
        f"- Blocked issues: {report.metrics.blocked_issues}",
        f"- Stale issues: {report.metrics.stale_issues}",
        "",
        "## Status Counts",
    ]
    lines.extend([f"- {key}: {value}" for key, value in sorted(report.metrics.status_counts.items())])
    lines.extend(["", "## Project Summary"])
    lines.extend([f"- {item.project}: total={item.total}, open={item.open_count}, closed={item.closed_count}, blocked={item.blocked_count}" for item in report.project_summaries])
    lines.extend(["", "## Priority Issues"])
    lines.extend([f"- {item.issue_key} | {item.status} | {item.assignee or '-'} | {item.priority or '-'} | {item.summary} | {item.change_summary}" for item in report.priority_issues])
    if daily_analysis:
        lines.extend(["", "## AI Daily Analysis", f"- Overall health: {daily_analysis.overall_health}"])
        for label, values in [
            ("Top risks", daily_analysis.top_risks),
            ("Suspected root causes", daily_analysis.suspected_root_causes),
            ("Recommended actions", daily_analysis.recommended_actions),
            ("Watch items", daily_analysis.watch_items),
        ]:
            lines.append(f"- {label}:")
            lines.extend([f"  - {value}" for value in values])
    if issue_analyses:
        lines.extend(["", "## Issue AI Analysis"])
        for issue_key, item in issue_analyses.items():
            lines.extend([
                f"### {issue_key}",
                f"- Summary: {item['summary']}",
                f"- Suspected root cause: {item['suspected_root_cause']}",
                f"- Confidence: {item['confidence']}",
                "- Evidence:",
            ])
            lines.extend([f"  - {value}" for value in item["evidence"]])
            lines.append("- Action needed:")
            lines.extend([f"  - {value}" for value in item["action_needed"]])
    return "\n".join(lines) + "\n"


def write_report_files(config: AppConfig, report: DailyReport, markdown_text: str, daily_analysis: DailyAIAnalysis | None, issue_analyses: dict[str, dict]) -> dict[str, str]:
    output_dir = Path(config.storage.output_dir) / "daily" / report.report_date
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "report.md"
    json_path = output_dir / "report.json"
    pdf_path = output_dir / "report.pdf"
    html_path = output_dir / "report.html"
    md_path.write_text(markdown_text, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                **report.to_dict(),
                "daily_analysis": daily_analysis.to_dict() if daily_analysis else None,
                "issue_analyses": issue_analyses,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pdf_written = render_pdf(config, report, daily_analysis, pdf_path, html_path)
    paths = {"markdown": str(md_path), "json": str(json_path), "html": str(html_path)}
    if pdf_written:
        paths["pdf"] = str(pdf_path)
    return paths


def render_pdf(config: AppConfig, report: DailyReport, daily_analysis: DailyAIAnalysis | None, pdf_path: Path, html_path: Path) -> bool:
    env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")), autoescape=select_autoescape(["html", "xml"]))
    html = env.get_template("report.html").render(report=report.to_dict(), daily_analysis=daily_analysis.to_dict() if daily_analysis else None)
    html_path.write_text(html, encoding="utf-8")
    try:
        from weasyprint import HTML
    except ImportError as exc:
        return False
    HTML(string=html).write_pdf(str(pdf_path))
    return True
