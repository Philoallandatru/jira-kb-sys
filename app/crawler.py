from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from app.config import JiraConfig
from app.models import IssueDelta, IssueRecord


class CrawlerError(RuntimeError):
    pass


@dataclass
class CrawlResult:
    snapshot_date: str
    issues: list[IssueRecord]


class JiraCrawler:
    def __init__(self, config: JiraConfig) -> None:
        self.config = config

    def crawl(self, snapshot_date: str | None = None) -> CrawlResult:
        snapshot_date = snapshot_date or date.today().isoformat()
        try:
            from jira import JIRA
        except ImportError as exc:
            raise CrawlerError("jira is not installed. Install with `pip install jira`.") from exc

        issues: dict[str, IssueRecord] = {}

        timeout_ms = self.config.timeout_seconds * 1000
        options = {"server": self.config.base_url, "timeout": timeout_ms}
        try:
            client = JIRA(options=options, token_auth=self.config.access_token.strip() or None)
        except Exception as exc:  # pragma: no cover - depends on runtime Jira connectivity
            raise CrawlerError(f"Failed to connect to Jira at {self.config.base_url}: {exc}") from exc

        for jira_filter in self.config.project_filters:
            query = self._extract_jql(jira_filter.url)
            if not query:
                continue
            for issue in self._search_issues(client, query, jira_filter.name):
                if issue.issue_key:
                    issues[issue.issue_key] = issue

        if self.config.jql:
            for issue in self._search_issues(client, self.config.jql, "default"):
                if issue.issue_key:
                    issues[issue.issue_key] = issue

        return CrawlResult(snapshot_date=snapshot_date, issues=list(issues.values()))

    def _extract_jql(self, url: str) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        jql = params.get("jql", [""])[0]
        return jql.strip()

    def _search_issues(self, client, jql: str, source_filter: str) -> list[IssueRecord]:
        try:
            result = client.search_issues(
                jql_str=jql,
                maxResults=self.config.max_results,
                fields="summary,status,assignee,priority,updated,created,labels,components,description",
            )
        except Exception as exc:  # pragma: no cover - depends on runtime Jira connectivity
            raise CrawlerError(f"Failed to query Jira by JQL `{jql}`: {exc}") from exc
        return [self._to_issue_record(item, source_filter) for item in result]

    def _to_issue_record(self, issue, source_filter: str) -> IssueRecord:
        fields = issue.fields
        return IssueRecord(
            issue_key=issue.key,
            summary=getattr(fields, "summary", "") or "",
            status=getattr(getattr(fields, "status", None), "name", "Unknown") or "Unknown",
            assignee=getattr(getattr(fields, "assignee", None), "displayName", None),
            priority=getattr(getattr(fields, "priority", None), "name", None),
            updated_at=getattr(fields, "updated", None),
            created_at=getattr(fields, "created", None),
            labels=list(getattr(fields, "labels", []) or []),
            components=[comp.name for comp in (getattr(fields, "components", []) or []) if getattr(comp, "name", None)],
            description=self._extract_description(getattr(fields, "description", None)),
            project=issue.key.split("-")[0] if issue.key else None,
            source_filter=source_filter,
        )

    def _extract_description(self, description) -> str | None:
        if description is None:
            return None
        if isinstance(description, str):
            return description
        if isinstance(description, dict):
            values: list[str] = []
            for block in description.get("content", []):
                for node in block.get("content", []):
                    text = node.get("text")
                    if text:
                        values.append(text)
            return "\n".join(values) or None
        return str(description)


def derive_issue_deltas(current: Iterable[IssueRecord], previous: Iterable[IssueRecord]) -> list[IssueDelta]:
    prev_map = {item.issue_key: item for item in previous}
    current_map = {item.issue_key: item for item in current}
    deltas: list[IssueDelta] = []
    for issue in current:
        prev = prev_map.get(issue.issue_key)
        if prev is None:
            deltas.append(IssueDelta(issue_key=issue.issue_key, change_type="new", current_status=issue.status, details="New issue"))
            continue
        if prev.status != issue.status:
            change_type = "closed" if issue.status.lower() in {"done", "closed", "resolved"} else "status_changed"
            deltas.append(
                IssueDelta(
                    issue_key=issue.issue_key,
                    change_type=change_type,
                    previous_status=prev.status,
                    current_status=issue.status,
                    details=f"Status changed from {prev.status} to {issue.status}",
                )
            )
        if prev.assignee != issue.assignee:
            deltas.append(
                IssueDelta(
                    issue_key=issue.issue_key,
                    change_type="assignee_changed",
                    previous_assignee=prev.assignee,
                    current_assignee=issue.assignee,
                    details=f"Assignee changed from {prev.assignee or '-'} to {issue.assignee or '-'}",
                )
            )
    for issue_key, prev in prev_map.items():
        if issue_key not in current_map:
            deltas.append(
                IssueDelta(
                    issue_key=issue_key,
                    change_type="missing",
                    previous_status=prev.status,
                    details="Issue missing from current snapshot",
                )
            )
    return deltas
