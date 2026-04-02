from __future__ import annotations

import json
from dataclasses import replace
from typing import Iterable

from app.config import DocsConfig
from app.docs import chunk_markdown
from app.models import DailyAIAnalysis, DocChunk, IssueAIAnalysis, IssueRecord, MarkdownDocument, utc_now_iso
from app.repository import Repository
from app.retrieval.preprocess import extract_exact_terms

JIRA_SOURCE_PREFIX = "jira_"


def build_jira_chunks(repo: Repository, docs_config: DocsConfig) -> list[DocChunk]:
    chunks: list[DocChunk] = []
    snapshot_dates = repo.list_snapshot_dates()

    for snapshot_date in snapshot_dates:
        issues = repo.load_snapshot(snapshot_date)
        analyses = {item.issue_key: item for item in repo.load_issue_analyses(snapshot_date)}

        for issue in issues:
            chunks.extend(
                _build_issue_chunks(
                    issue=issue,
                    snapshot_date=snapshot_date,
                    issue_analysis=analyses.get(issue.issue_key),
                    docs_config=docs_config,
                )
            )

        daily_analysis = repo.load_daily_analysis(snapshot_date)
        if daily_analysis:
            chunks.extend(_build_daily_analysis_chunks(snapshot_date, daily_analysis, docs_config))

    return chunks


def filter_product_doc_chunks(chunks: list[DocChunk]) -> list[DocChunk]:
    return [chunk for chunk in chunks if not chunk.source_type.startswith(JIRA_SOURCE_PREFIX)]


def filter_jira_doc_chunks(chunks: list[DocChunk]) -> list[DocChunk]:
    return [chunk for chunk in chunks if chunk.source_type.startswith(JIRA_SOURCE_PREFIX)]


def _build_issue_chunks(
    issue: IssueRecord,
    snapshot_date: str,
    issue_analysis: IssueAIAnalysis | None,
    docs_config: DocsConfig,
) -> list[DocChunk]:
    documents: list[MarkdownDocument] = [
        MarkdownDocument(
            document_id=_issue_document_id(issue.issue_key, snapshot_date),
            source_path=f"jira://snapshot/{snapshot_date}/{issue.issue_key}",
            source_type="jira_issue",
            title=f"{issue.issue_key} snapshot",
            markdown_path=f"jira://markdown/{snapshot_date}/{issue.issue_key}",
            content=_render_issue_markdown(issue, snapshot_date),
            updated_at=utc_now_iso(),
            metadata=_issue_document_metadata(issue, snapshot_date),
        )
    ]
    if issue_analysis:
        documents.append(
            MarkdownDocument(
                document_id=_issue_analysis_document_id(issue.issue_key, snapshot_date),
                source_path=f"jira://analysis/{snapshot_date}/{issue.issue_key}",
                source_type="jira_issue_analysis",
                title=f"{issue.issue_key} analysis",
                markdown_path=f"jira://markdown-analysis/{snapshot_date}/{issue.issue_key}",
                content=_render_issue_analysis_markdown(issue_analysis),
                updated_at=utc_now_iso(),
                metadata={
                    **_issue_document_metadata(issue, snapshot_date),
                    "source_id": f"jira-analysis:{issue.issue_key}:{snapshot_date}",
                },
            )
        )

    chunks: list[DocChunk] = []
    for document in documents:
        current_chunks = list(chunk_markdown(document, docs_config.max_chunk_chars, docs_config.overlap_chars))
        chunks.extend(_retag_source_type(current_chunks, document.source_type, issue))
    return chunks


def _build_daily_analysis_chunks(
    snapshot_date: str,
    daily_analysis: DailyAIAnalysis,
    docs_config: DocsConfig,
) -> list[DocChunk]:
    document = MarkdownDocument(
        document_id=f"jira-daily-analysis-{snapshot_date}",
        source_path=f"jira://daily-analysis/{snapshot_date}",
        source_type="jira_daily_analysis",
        title=f"Daily analysis {snapshot_date}",
        markdown_path=f"jira://markdown-daily-analysis/{snapshot_date}",
        content=_render_daily_analysis_markdown(daily_analysis),
        updated_at=utc_now_iso(),
        metadata={
            "source_id": f"jira-daily:{snapshot_date}",
            "page_title": f"Daily analysis {snapshot_date}",
            "labels": ["jira", "daily-analysis"],
            "ancestor_titles": ["Jira Daily Analyses"],
            "authors": [],
            "comment_snippets": [],
        },
    )
    return _retag_source_type(
        list(chunk_markdown(document, docs_config.max_chunk_chars, docs_config.overlap_chars)),
        document.source_type,
        None,
    )


def _retag_source_type(chunks: list[DocChunk], source_type: str, issue: IssueRecord | None) -> list[DocChunk]:
    normalized = source_type if source_type.startswith(JIRA_SOURCE_PREFIX) else f"{JIRA_SOURCE_PREFIX}{source_type}"
    extra_tags = _issue_search_tags(issue) if issue else []
    return [
        replace(
            chunk,
            source_type=normalized,
            exact_terms=list(dict.fromkeys([*chunk.exact_terms, *extra_tags])),
            tags=list(dict.fromkeys([*chunk.tags, *extra_tags])),
        )
        for chunk in chunks
    ]


def _render_issue_markdown(issue: IssueRecord, snapshot_date: str) -> str:
    lines = [
        f"# Jira Issue Snapshot: {issue.issue_key}",
        "",
        "## Metadata",
        f"- Snapshot Date: {snapshot_date}",
        f"- Status: {issue.status}",
        f"- Team: {issue.team or 'Unknown'}",
        f"- Assignee: {issue.assignee or 'Unassigned'}",
        f"- Priority: {issue.priority or 'Unknown'}",
        f"- Type: {issue.issue_type or 'Unknown'}",
        f"- Resolution: {issue.resolution or 'Unresolved'}",
        f"- Fix Versions: {', '.join(issue.fix_versions) if issue.fix_versions else 'None'}",
        f"- Affects Versions: {', '.join(issue.affects_versions) if issue.affects_versions else 'None'}",
        f"- Severity: {issue.severity or 'Unknown'}",
        f"- Report Department: {issue.report_department or 'Unknown'}",
        f"- Root Cause: {issue.root_cause or 'Unknown'}",
        f"- Frequency: {issue.frequency or 'Unknown'}",
        f"- Fail Runtime: {issue.fail_runtime or 'Unknown'}",
        f"- Project: {issue.project or 'Unknown'}",
        f"- Labels: {', '.join(issue.labels) if issue.labels else 'None'}",
        f"- Components: {', '.join(issue.components) if issue.components else 'None'}",
        f"- Updated At: {issue.updated_at or 'Unknown'}",
        f"- Created At: {issue.created_at or 'Unknown'}",
        "",
        "## Summary",
        issue.summary,
        "",
    ]
    if issue.description_fields:
        lines.extend(["## Structured Description"])
        for key, value in issue.description_fields.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
    if issue.description:
        lines.extend(["## Description", issue.description, ""])
    if issue.comments:
        lines.append("## Comments")
        lines.extend(f"- {comment}" for comment in issue.comments)
        lines.append("")
    if issue.activity_comments:
        lines.append("## Activity Comments")
        lines.extend(f"- {comment}" for comment in issue.activity_comments)
        lines.append("")
    if issue.activity_all:
        lines.append("## Activity All")
        lines.extend(f"- {item}" for item in issue.activity_all)
        lines.append("")
    if issue.blocks_links:
        lines.append("## Blocks")
        lines.extend(f"- {link}" for link in issue.blocks_links)
        lines.append("")
    if issue.mentioned_in_links:
        lines.append("## Mentioned In")
        lines.extend(f"- {link}" for link in issue.mentioned_in_links)
        lines.append("")
    if issue.issue_links:
        lines.append("## Issue Links")
        lines.extend(f"- {link}" for link in issue.issue_links)
        lines.append("")
    if issue.links:
        lines.append("## Links")
        lines.extend(f"- {link}" for link in issue.links)
        lines.append("")
    lines.extend(["## Raw JSON", "```json", json.dumps(issue.to_dict(), ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def _render_issue_analysis_markdown(issue_analysis: IssueAIAnalysis) -> str:
    lines = [
        f"# Jira Issue Analysis: {issue_analysis.issue_key}",
        "",
        "## Summary",
        issue_analysis.summary,
        "",
        "## Suspected Root Cause",
        issue_analysis.suspected_root_cause,
        "",
        "## Evidence",
    ]
    lines.extend(f"- {item}" for item in (issue_analysis.evidence or ["None"]))
    lines.extend(["", "## Action Needed"])
    lines.extend(f"- {item}" for item in (issue_analysis.action_needed or ["None"]))
    lines.extend(["", "## Confidence", issue_analysis.confidence, ""])
    return "\n".join(lines)


def _render_daily_analysis_markdown(daily_analysis: DailyAIAnalysis) -> str:
    lines = [
        f"# Jira Daily Analysis: {daily_analysis.report_date}",
        "",
        "## Overall Health",
        daily_analysis.overall_health,
        "",
        "## Top Risks",
    ]
    lines.extend(f"- {item}" for item in (daily_analysis.top_risks or ["None"]))
    lines.extend(["", "## Suspected Root Causes"])
    lines.extend(f"- {item}" for item in (daily_analysis.suspected_root_causes or ["None"]))
    lines.extend(["", "## Recommended Actions"])
    lines.extend(f"- {item}" for item in (daily_analysis.recommended_actions or ["None"]))
    lines.extend(["", "## Watch Items"])
    lines.extend(f"- {item}" for item in (daily_analysis.watch_items or ["None"]))
    lines.append("")
    return "\n".join(lines)


def _issue_document_id(issue_key: str, snapshot_date: str) -> str:
    return f"jira-issue-{snapshot_date}-{issue_key.lower().replace('[', '').replace(']', '').replace('/', '-')}"


def _issue_analysis_document_id(issue_key: str, snapshot_date: str) -> str:
    return f"jira-issue-analysis-{snapshot_date}-{issue_key.lower().replace('[', '').replace(']', '').replace('/', '-')}"


def _issue_search_tags(issue: IssueRecord | None) -> list[str]:
    if issue is None:
        return []
    values: list[str] = []
    for item in [
        issue.issue_type,
        issue.severity,
        issue.report_department,
        issue.root_cause,
        issue.frequency,
        issue.fail_runtime,
        *issue.components,
        *issue.fix_versions,
        *issue.affects_versions,
    ]:
        if not item:
            continue
        values.extend(_tokenize_tag(item))
    for key in ["Platform Name", "Script Name", "Firmware Version", "Density", "Form Factor"]:
        if issue.description_fields.get(key):
            values.extend(_tokenize_tag(issue.description_fields[key]))
    values.extend(extract_exact_terms(issue.summary))
    values.extend(extract_exact_terms(issue.description or ""))
    return list(dict.fromkeys(values))


def _issue_document_metadata(issue: IssueRecord, snapshot_date: str) -> dict[str, object]:
    return {
        "source_id": f"jira:{issue.issue_key}:{snapshot_date}",
        "page_title": f"{issue.issue_key} snapshot",
        "ancestor_titles": ["Jira", snapshot_date],
        "labels": [*issue.labels, *(issue.components or []), issue.status, issue.severity or "", issue.root_cause or ""],
        "authors": [issue.assignee] if issue.assignee else [],
        "comment_snippets": list(issue.comments[:3]),
        "issue_key": issue.issue_key,
        "team": issue.team,
        "severity": issue.severity,
        "root_cause": issue.root_cause,
        "fix_versions": issue.fix_versions,
        "affects_versions": issue.affects_versions,
        "platform_name": issue.description_fields.get("Platform Name"),
        "script_name": issue.description_fields.get("Script Name"),
        "firmware_version": issue.description_fields.get("Firmware Version"),
    }


def _tokenize_tag(text: str) -> Iterable[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return [collapsed] if collapsed else []
