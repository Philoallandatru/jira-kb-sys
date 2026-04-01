from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from app.config import JiraConfig
from app.models import IssueChangeEvent, IssueDelta, IssueRecord, infer_team_from_issue_key


class CrawlerError(RuntimeError):
    pass


@dataclass
class CrawlResult:
    snapshot_date: str
    issues: list[IssueRecord]
    change_events: list[IssueChangeEvent]


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
        change_events: dict[str, IssueChangeEvent] = {}
        options = {"server": self.config.base_url, "timeout": self.config.timeout_seconds}
        try:
            client = JIRA(options=options, token_auth=self.config.access_token.strip() or None)
        except Exception as exc:  # pragma: no cover
            raise CrawlerError(f"Failed to connect to Jira at {self.config.base_url}: {exc}") from exc

        for jira_filter in self.config.project_filters:
            query = self._extract_jql(jira_filter.url)
            if not query:
                continue
            records, events = self._search_issues(client, query, jira_filter.name)
            for issue in records:
                issues[issue.issue_key] = issue
            for event in events:
                change_events[event.event_id] = event

        if self.config.jql:
            records, events = self._search_issues(client, self.config.jql, "default")
            for issue in records:
                issues[issue.issue_key] = issue
            for event in events:
                change_events[event.event_id] = event

        return CrawlResult(snapshot_date=snapshot_date, issues=list(issues.values()), change_events=list(change_events.values()))

    def _extract_jql(self, url: str) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return params.get("jql", [""])[0].strip()

    def _search_issues(self, client, jql: str, source_filter: str) -> tuple[list[IssueRecord], list[IssueChangeEvent]]:
        try:
            result = client.search_issues(
                jql_str=jql,
                maxResults=self.config.max_results,
                fields="summary,status,assignee,priority,updated,created,labels,components,description",
                expand="changelog",
            )
        except Exception as exc:  # pragma: no cover
            raise CrawlerError(f"Failed to query Jira by JQL `{jql}`: {exc}") from exc
        records = [self._to_issue_record(item, source_filter) for item in result]
        events = [event for item in result for event in self._extract_change_events(item)]
        return records, events

    def _to_issue_record(self, issue, source_filter: str) -> IssueRecord:
        fields = issue.fields
        issue_key = issue.key
        return IssueRecord(
            issue_key=issue_key,
            summary=getattr(fields, "summary", "") or "",
            status=getattr(getattr(fields, "status", None), "name", "Unknown") or "Unknown",
            team=infer_team_from_issue_key(issue_key),
            assignee=getattr(getattr(fields, "assignee", None), "displayName", None),
            priority=getattr(getattr(fields, "priority", None), "name", None),
            updated_at=getattr(fields, "updated", None),
            created_at=getattr(fields, "created", None),
            labels=list(getattr(fields, "labels", []) or []),
            components=[comp.name for comp in (getattr(fields, "components", []) or []) if getattr(comp, "name", None)],
            description=self._extract_description(getattr(fields, "description", None)),
            project=issue_key.split("-")[0] if issue_key else None,
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

    def _extract_change_events(self, issue) -> list[IssueChangeEvent]:
        changelog = getattr(issue, "changelog", None)
        histories = getattr(changelog, "histories", None)
        if not histories:
            return []
        events: list[IssueChangeEvent] = []
        for history in histories:
            history_id = str(getattr(history, "id", ""))
            changed_at = getattr(history, "created", None) or ""
            author = getattr(getattr(history, "author", None), "displayName", None)
            for index, item in enumerate(getattr(history, "items", []) or []):
                field = str(getattr(item, "field", "") or "")
                from_value = getattr(item, "fromString", None)
                to_value = getattr(item, "toString", None)
                events.append(
                    IssueChangeEvent(
                        event_id=f"{issue.key}:{history_id}:{index}:{field}",
                        issue_key=issue.key,
                        changed_at=changed_at,
                        author=author,
                        field=field,
                        from_value=from_value,
                        to_value=to_value,
                        change_type=self._change_type(field, from_value, to_value),
                        issue_status_after=to_value if field.lower() == "status" else None,
                        team_after=infer_team_from_issue_key(issue.key),
                    )
                )
        return events

    def _change_type(self, field: str, from_value: str | None, to_value: str | None) -> str:
        field_lower = field.lower()
        if field_lower == "status":
            from_status = (from_value or "").lower()
            to_status = (to_value or "").lower()
            if to_status in {"done", "closed", "resolved"}:
                return "closed"
            if from_status in {"done", "closed", "resolved"} and to_status not in {"done", "closed", "resolved"}:
                return "reopened"
            return "status_changed"
        if field_lower == "assignee":
            return "assignee_changed"
        return f"{field_lower}_changed"


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
            prev_closed = prev.status.lower() in {"done", "closed", "resolved"}
            current_closed = issue.status.lower() in {"done", "closed", "resolved"}
            if current_closed:
                change_type = "closed"
            elif prev_closed and not current_closed:
                change_type = "reopened"
            else:
                change_type = "status_changed"
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


def reconstruct_snapshot_issues(
    issues: Iterable[IssueRecord],
    change_events: Iterable[IssueChangeEvent],
    snapshot_date: str,
) -> list[IssueRecord]:
    target_end = _target_day_end(snapshot_date)
    events_by_issue: dict[str, list[IssueChangeEvent]] = {}
    for event in change_events:
        events_by_issue.setdefault(event.issue_key, []).append(event)

    reconstructed: list[IssueRecord] = []
    for issue in issues:
        created_at = _parse_jira_datetime(issue.created_at)
        if created_at and created_at > target_end:
            continue
        current = replace(issue)
        future_events = [
            event
            for event in events_by_issue.get(issue.issue_key, [])
            if (_parse_jira_datetime(event.changed_at) or target_end) > target_end
        ]
        future_events.sort(key=lambda item: _parse_jira_datetime(item.changed_at) or target_end, reverse=True)
        for event in future_events:
            field = event.field.lower()
            if field == "status" and event.from_value:
                current.status = event.from_value
            elif field == "assignee":
                current.assignee = event.from_value
        reconstructed.append(current)

    reconstructed.sort(key=lambda item: item.issue_key)
    return reconstructed


def iter_snapshot_dates(date_from: str, date_to: str) -> list[str]:
    start = datetime.fromisoformat(date_from).date()
    end = datetime.fromisoformat(date_to).date()
    if end < start:
        raise CrawlerError("date_to must be on or after date_from")
    values: list[str] = []
    current = start
    while current <= end:
        values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def _target_day_end(snapshot_date: str) -> datetime:
    return datetime.combine(datetime.fromisoformat(snapshot_date).date(), time.max).replace(tzinfo=timezone.utc)


def _parse_jira_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt).astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
