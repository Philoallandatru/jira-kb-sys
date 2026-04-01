from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def infer_team_from_issue_key(issue_key: str) -> str | None:
    key = issue_key.strip().upper()
    if key.startswith("[SV]"):
        return "SV"
    if key.startswith("[DV]"):
        return "DV"
    return None


@dataclass
class IssueRecord:
    issue_key: str
    summary: str
    status: str
    team: str | None = None
    assignee: str | None = None
    priority: str | None = None
    project: str | None = None
    labels: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    description: str | None = None
    comments: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    issue_type: str | None = None
    resolution: str | None = None
    fix_versions: list[str] = field(default_factory=list)
    affects_versions: list[str] = field(default_factory=list)
    severity: str | None = None
    report_department: str | None = None
    root_cause: str | None = None
    frequency: str | None = None
    fail_runtime: str | None = None
    description_fields: dict[str, str] = field(default_factory=dict)
    activity_comments: list[str] = field(default_factory=list)
    activity_all: list[str] = field(default_factory=list)
    issue_links: list[str] = field(default_factory=list)
    mentioned_in_links: list[str] = field(default_factory=list)
    blocks_links: list[str] = field(default_factory=list)
    raw_fields: dict[str, Any] = field(default_factory=dict)
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
class IssueChangeEvent:
    event_id: str
    issue_key: str
    changed_at: str
    author: str | None
    field: str
    from_value: str | None
    to_value: str | None
    change_type: str
    issue_status_after: str | None = None
    team_after: str | None = None

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


@dataclass
class DeepAnalysisCitation:
    source_type: str
    source_path: str
    section_path: list[str]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IssueDeepAnalysisResult:
    issue_key: str
    generated_at: str
    issue_summary: str
    spec_relations: list[str]
    policy_relations: list[str]
    related_jira_designs: list[str]
    suspected_problems: list[str]
    next_actions: list[str]
    open_questions: list[str]
    confidence: str
    citations: list[DeepAnalysisCitation]
    raw_response: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_key": self.issue_key,
            "generated_at": self.generated_at,
            "issue_summary": self.issue_summary,
            "spec_relations": self.spec_relations,
            "policy_relations": self.policy_relations,
            "related_jira_designs": self.related_jira_designs,
            "suspected_problems": self.suspected_problems,
            "next_actions": self.next_actions,
            "open_questions": self.open_questions,
            "confidence": self.confidence,
            "citations": [item.to_dict() for item in self.citations],
            "raw_response": self.raw_response,
        }


@dataclass
class ManagementSummaryRequest:
    date_from: str
    date_to: str
    team: str | None = None
    jira_status: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ManagementSummaryMetrics:
    updated_issue_count: int
    status_progress_count: int
    closed_count: int
    reopened_count: int
    assignee_change_count: int
    blocked_count: int
    high_priority_open_count: int
    team_distribution: dict[str, int]
    status_distribution: dict[str, int]
    issue_type_distribution: dict[str, int]
    severity_distribution: dict[str, int]
    root_cause_distribution: dict[str, int]
    report_department_distribution: dict[str, int]
    component_distribution: dict[str, int]
    issues_without_owner: int
    issues_without_root_cause: int
    issues_without_fix_version: int
    issues_without_repro_context: int
    referenced_issue_keys: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ManagementSummaryResult:
    summary_id: int | None
    generated_at: str
    request: ManagementSummaryRequest
    metrics: ManagementSummaryMetrics
    latest_progress_overview: list[str]
    key_recent_changes: list[str]
    current_risks_and_blockers: list[str]
    root_cause_and_pattern_observations: list[str]
    recommended_management_actions: list[str]
    data_gaps: list[str]
    referenced_issue_keys: list[str]
    referenced_metrics: dict[str, int | float | str]
    raw_response: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "generated_at": self.generated_at,
            "request": self.request.to_dict(),
            "metrics": self.metrics.to_dict(),
            "latest_progress_overview": self.latest_progress_overview,
            "key_recent_changes": self.key_recent_changes,
            "current_risks_and_blockers": self.current_risks_and_blockers,
            "root_cause_and_pattern_observations": self.root_cause_and_pattern_observations,
            "recommended_management_actions": self.recommended_management_actions,
            "data_gaps": self.data_gaps,
            "referenced_issue_keys": self.referenced_issue_keys,
            "referenced_metrics": self.referenced_metrics,
            "raw_response": self.raw_response,
        }


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
