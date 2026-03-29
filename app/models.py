from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class IssueRecord:
    issue_key: str
    summary: str
    status: str
    assignee: str | None = None
    priority: str | None = None
    project: str | None = None
    labels: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    description: str | None = None
    comments: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    updated_at: str | None = None
    created_at: str | None = None
    source_filter: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IssueDelta:
    issue_key: str
    change_type: str
    previous_status: str | None = None
    current_status: str | None = None
    previous_assignee: str | None = None
    current_assignee: str | None = None
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MarkdownDocument:
    document_id: str
    source_path: str
    source_type: str
    title: str
    markdown_path: str
    content: str
    updated_at: str


@dataclass
class DocChunk:
    chunk_id: str
    source_path: str
    source_type: str
    doc_title: str
    section_path: list[str]
    page_or_sheet: str | None
    content: str
    tags: list[str]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriorityIssue:
    issue_key: str
    summary: str
    status: str
    assignee: str | None
    priority: str | None
    change_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyMetrics:
    total_issues: int
    new_issues: int
    closed_issues: int
    blocked_issues: int
    stale_issues: int
    status_counts: dict[str, int]

    @classmethod
    def from_issues(cls, issues: list[IssueRecord], deltas: list[IssueDelta], stale_issue_keys: set[str]) -> "DailyMetrics":
        status_counts = dict(Counter(issue.status for issue in issues if issue.status))
        return cls(
            total_issues=len(issues),
            new_issues=sum(1 for delta in deltas if delta.change_type == "new"),
            closed_issues=sum(1 for delta in deltas if delta.change_type == "closed"),
            blocked_issues=sum(1 for issue in issues if "block" in issue.status.lower() or "blocker" in " ".join(issue.labels).lower()),
            stale_issues=len(stale_issue_keys),
            status_counts=status_counts,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectSummary:
    project: str
    total: int
    open_count: int
    closed_count: int
    blocked_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyReport:
    report_date: str
    generated_at: str
    run_id: int | None
    metrics: DailyMetrics
    project_summaries: list[ProjectSummary]
    priority_issues: list[PriorityIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_date": self.report_date,
            "generated_at": self.generated_at,
            "run_id": self.run_id,
            "metrics": self.metrics.to_dict(),
            "project_summaries": [item.to_dict() for item in self.project_summaries],
            "priority_issues": [item.to_dict() for item in self.priority_issues],
        }


@dataclass
class DailyAIAnalysis:
    report_date: str
    overall_health: str
    top_risks: list[str]
    suspected_root_causes: list[str]
    recommended_actions: list[str]
    watch_items: list[str]
    raw_response: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IssueAIAnalysis:
    report_date: str
    issue_key: str
    summary: str
    suspected_root_cause: str
    evidence: list[str]
    action_needed: list[str]
    confidence: str
    raw_response: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
