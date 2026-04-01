from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable
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

    def check_connection(self) -> dict[str, object]:
        client = self._build_client()
        server_info = {}
        myself = None
        try:
            server_info = client.server_info() or {}
        except Exception:
            server_info = {}
        try:
            myself = client.myself()
        except Exception:
            myself = None
        authenticated_user = None
        if isinstance(myself, dict):
            authenticated_user = myself.get("displayName") or myself.get("name")
        return {
            "ok": True,
            "base_url": self.config.base_url,
            "server_title": server_info.get("serverTitle"),
            "version": server_info.get("version"),
            "deployment_type": server_info.get("deploymentType"),
            "authenticated_user": authenticated_user,
            "project_filter_count": len(self.config.project_filters),
            "has_jql": bool(self.config.jql.strip()),
        }

    def crawl(self, snapshot_date: str | None = None) -> CrawlResult:
        snapshot_date = snapshot_date or date.today().isoformat()
        issues: dict[str, IssueRecord] = {}
        change_events: dict[str, IssueChangeEvent] = {}
        client = self._build_client()

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

    def _build_client(self):
        try:
            from jira import JIRA
        except ImportError as exc:
            raise CrawlerError("jira is not installed. Install with `pip install jira`.") from exc

        options = {"server": self.config.base_url, "timeout": self.config.timeout_seconds}
        try:
            return JIRA(options=options, token_auth=self.config.access_token.strip() or None)
        except Exception as exc:  # pragma: no cover
            raise CrawlerError(f"Failed to connect to Jira at {self.config.base_url}: {exc}") from exc

    def _extract_jql(self, url: str) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return params.get("jql", [""])[0].strip()

    def _search_issues(self, client, jql: str, source_filter: str) -> tuple[list[IssueRecord], list[IssueChangeEvent]]:
        fields = [
            "summary",
            "status",
            "assignee",
            "priority",
            "updated",
            "created",
            "labels",
            "components",
            "description",
            "issuetype",
            "resolution",
            "fixVersions",
            "versions",
            "comment",
            "issuelinks",
        ]
        mapped_fields = [value for value in self.config.field_mapping.model_dump().values() if value]
        fields.extend(mapped_fields)
        try:
            result = client.search_issues(
                jql_str=jql,
                maxResults=self.config.max_results,
                fields=",".join(dict.fromkeys(fields)),
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
        description_text, description_fields = self._extract_description_payload(self._field_value(fields, "description"))
        comments = self._extract_comments(fields)
        issue_links, blocks_links, mentioned_in_links = self._extract_issue_links(fields)
        mapped_values = self._extract_mapped_fields(fields)
        fix_versions = self._extract_name_list(self._field_value(fields, "fixVersions"))
        affects_versions = self._extract_name_list(self._field_value(fields, "versions"))
        activity_comments = self._ensure_text_list(mapped_values.get("activity_comment")) or comments
        activity_all = self._ensure_text_list(mapped_values.get("activity_all")) or [*comments, *issue_links]
        return IssueRecord(
            issue_key=issue_key,
            summary=self._as_text(self._field_value(fields, "summary")),
            status=self._as_named_value(self._field_value(fields, "status")) or "Unknown",
            team=infer_team_from_issue_key(issue_key),
            assignee=self._as_display_name(self._field_value(fields, "assignee")),
            priority=self._as_named_value(self._field_value(fields, "priority")),
            updated_at=self._field_value(fields, "updated"),
            created_at=self._field_value(fields, "created"),
            labels=self._ensure_text_list(self._field_value(fields, "labels")),
            components=self._extract_name_list(self._field_value(fields, "components")),
            description=description_text,
            comments=comments,
            links=issue_links,
            issue_type=self._as_named_value(self._field_value(fields, "issuetype")) or self._as_text(mapped_values.get("issue_type")),
            resolution=self._as_named_value(self._field_value(fields, "resolution")),
            fix_versions=fix_versions,
            affects_versions=affects_versions,
            severity=self._as_text(mapped_values.get("severity")),
            report_department=self._as_text(mapped_values.get("report_department")),
            root_cause=self._as_text(mapped_values.get("root_cause")),
            frequency=self._as_text(mapped_values.get("frequency")),
            fail_runtime=self._as_text(mapped_values.get("fail_runtime")),
            description_fields=self._merge_description_fields(description_fields, mapped_values),
            activity_comments=activity_comments,
            activity_all=activity_all,
            issue_links=issue_links,
            mentioned_in_links=mentioned_in_links,
            blocks_links=blocks_links,
            raw_fields={key: self._serialize_raw_field(value) for key, value in mapped_values.items() if value not in (None, "", [], {})},
            project=issue_key.split("-")[0] if issue_key else None,
            source_filter=source_filter,
        )

    def _extract_description_payload(self, description) -> tuple[str | None, dict[str, str]]:
        if description is None:
            return None, {}
        if isinstance(description, str):
            return description, self._parse_key_value_text(description)
        if isinstance(description, dict):
            fields = self._extract_adf_table_fields(description)
            text = self._extract_adf_text(description)
            if not fields:
                fields = self._parse_key_value_text(text)
            return text or None, fields
        text = str(description)
        return text, self._parse_key_value_text(text)

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

    def _extract_mapped_fields(self, fields) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for logical_name, field_id in self.config.field_mapping.model_dump().items():
            if not field_id:
                continue
            values[logical_name] = self._field_value(fields, field_id)
        return values

    def _field_value(self, fields, name: str) -> Any:
        if isinstance(fields, dict):
            if name in fields:
                return fields.get(name)
            lowered = name.lower()
            for key, value in fields.items():
                if str(key).lower() == lowered:
                    return value
            return None
        if hasattr(fields, name):
            return getattr(fields, name)
        lowered = name.lower()
        for attr in dir(fields):
            if attr.lower() == lowered:
                return getattr(fields, attr)
        return None

    def _extract_comments(self, fields) -> list[str]:
        comment_field = self._field_value(fields, "comment")
        comments = getattr(comment_field, "comments", None) if comment_field is not None else None
        if comments is None and isinstance(comment_field, dict):
            comments = comment_field.get("comments", [])
        extracted: list[str] = []
        for item in comments or []:
            body = getattr(item, "body", None) if not isinstance(item, dict) else item.get("body")
            text, _ = self._extract_description_payload(body)
            if text:
                extracted.append(text)
        return extracted

    def _extract_issue_links(self, fields) -> tuple[list[str], list[str], list[str]]:
        links = self._field_value(fields, "issuelinks") or []
        issue_links: list[str] = []
        blocks_links: list[str] = []
        mentioned_links: list[str] = []
        for item in links:
            link_type = self._as_text(getattr(getattr(item, "type", None), "name", None) or getattr(item, "type", None))
            outward_issue = getattr(item, "outwardIssue", None)
            inward_issue = getattr(item, "inwardIssue", None)
            target = outward_issue or inward_issue
            if target is None and isinstance(item, dict):
                link_type = self._as_text(((item.get("type") or {}).get("name")) or link_type)
                target = item.get("outwardIssue") or item.get("inwardIssue")
            target_key = self._as_text(getattr(target, "key", None) if not isinstance(target, dict) else target.get("key"))
            target_summary = ""
            if target:
                target_fields = getattr(target, "fields", None) if not isinstance(target, dict) else target.get("fields")
                target_summary = self._as_text(
                    getattr(target_fields, "summary", None) if not isinstance(target_fields, dict) else target_fields.get("summary")
                )
            text = " | ".join(part for part in [target_key, target_summary, link_type] if part)
            if not text:
                continue
            issue_links.append(text)
            lowered = link_type.lower()
            if "block" in lowered:
                blocks_links.append(text)
            if "mention" in lowered or "refer" in lowered:
                mentioned_links.append(text)
        return issue_links, blocks_links, mentioned_links

    def _extract_name_list(self, values) -> list[str]:
        if not values:
            return []
        if isinstance(values, list):
            result = []
            for item in values:
                result.append(self._as_named_value(item) or self._as_text(item))
            return [item for item in result if item]
        return [self._as_named_value(values) or self._as_text(values)] if values else []

    def _as_text(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            for key in ("value", "name", "displayName", "text"):
                if value.get(key):
                    return str(value.get(key)).strip()
            return str(value)
        for key in ("value", "name", "displayName", "text"):
            attr = getattr(value, key, None)
            if attr:
                return str(attr).strip()
        return str(value).strip() or None

    def _as_named_value(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, dict):
            for key in ("name", "value"):
                if value.get(key):
                    return str(value.get(key)).strip()
        for key in ("name", "value"):
            attr = getattr(value, key, None)
            if attr:
                return str(attr).strip()
        return self._as_text(value)

    def _as_display_name(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return self._as_text(value.get("displayName") or value.get("name"))
        return self._as_text(getattr(value, "displayName", None) or getattr(value, "name", None))

    def _extract_adf_text(self, document: dict[str, Any]) -> str:
        lines: list[str] = []

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                node_type = node.get("type")
                if node_type == "text" and node.get("text"):
                    lines.append(str(node.get("text")))
                elif node_type in {"paragraph", "heading", "tableCell", "tableHeader"}:
                    before = len(lines)
                    for child in node.get("content", []):
                        visit(child)
                    if len(lines) > before:
                        lines.append("\n")
                else:
                    for child in node.get("content", []):
                        visit(child)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(document)
        text = "".join(lines)
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return text

    def _extract_adf_table_fields(self, document: dict[str, Any]) -> dict[str, str]:
        extracted: dict[str, str] = {}

        def gather_cell_text(cell: dict[str, Any]) -> str:
            return self._extract_adf_text({"type": "doc", "content": cell.get("content", [])}).strip()

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") == "table":
                    for row in node.get("content", []):
                        if row.get("type") != "tableRow":
                            continue
                        cells = [gather_cell_text(cell) for cell in row.get("content", [])]
                        cells = [cell for cell in cells if cell]
                        if len(cells) >= 2:
                            extracted[self._normalize_description_key(cells[0])] = " | ".join(cells[1:])
                for child in node.get("content", []):
                    visit(child)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(document)
        return extracted

    def _parse_key_value_text(self, text: str) -> dict[str, str]:
        extracted: dict[str, str] = {}
        for line in text.splitlines():
            normalized = line.strip().lstrip("-*").strip()
            if ":" not in normalized:
                continue
            key, value = normalized.split(":", 1)
            key = self._normalize_description_key(key)
            value = value.strip()
            if key and value:
                extracted[key] = value
        return extracted

    def _normalize_description_key(self, key: str) -> str:
        normalized = " ".join(key.replace("\u00a0", " ").split()).strip().lower()
        aliases = {
            "firmware version": "Firmware Version",
            "density": "Density",
            "form factor": "Form Factor",
            "platform name": "Platform Name",
            "platform nmae": "Platform Name",
            "script name": "Script Name",
            "test step": "Test step",
            "expect result": "Expect Result",
            "expected result": "Expect Result",
            "actual result": "Actual Result",
            "activity": "Activity",
            "comment": "Comment",
            "all": "All",
        }
        return aliases.get(normalized, key.strip())

    def _merge_description_fields(self, extracted: dict[str, str], mapped_values: dict[str, Any]) -> dict[str, str]:
        merged = dict(extracted)
        mapping_targets = {
            "firmware_version": "Firmware Version",
            "density": "Density",
            "form_factor": "Form Factor",
            "platform_name": "Platform Name",
            "script_name": "Script Name",
            "test_step": "Test step",
            "expect_result": "Expect Result",
            "actual_result": "Actual Result",
            "activity_comment": "Comment",
            "activity_all": "All",
        }
        for key, description_key in mapping_targets.items():
            value = self._as_text(mapped_values.get(key))
            if value:
                merged[description_key] = value
        return merged

    def _ensure_text_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in (self._as_text(entry) for entry in value) if item]
        text = self._as_text(value)
        if not text:
            return []
        if "\n" in text:
            return [line.strip("-* ").strip() for line in text.splitlines() if line.strip()]
        return [text]

    def _serialize_raw_field(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._serialize_raw_field(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_raw_field(item) for key, item in value.items()}
        if hasattr(value, "raw") and isinstance(value.raw, dict):
            return {key: self._serialize_raw_field(item) for key, item in value.raw.items()}
        if hasattr(value, "__dict__"):
            return {
                key: self._serialize_raw_field(item)
                for key, item in value.__dict__.items()
                if not key.startswith("_")
            }
        return str(value)

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
