from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

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
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise CrawlerError("Playwright is not installed. Install with `pip install -e .[playwright]`.") from exc

        issues: dict[str, IssueRecord] = {}
        auth_path = Path(self.config.auth_state_path)
        auth_path.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(auth_path)) if auth_path.exists() else browser.new_context()
            page = context.new_page()
            page.set_default_timeout(self.config.timeout_seconds * 1000)
            if not auth_path.exists():
                self._login(page)
                context.storage_state(path=str(auth_path))
            for jira_filter in self.config.project_filters:
                try:
                    page.goto(jira_filter.url, wait_until="networkidle")
                except PlaywrightTimeoutError as exc:
                    raise CrawlerError(f"Timeout loading Jira filter {jira_filter.name}") from exc
                for row in page.locator(self.config.list_selector).all():
                    issue = self._parse_issue_row(row, jira_filter.name)
                    if issue.issue_key:
                        issues[issue.issue_key] = issue
            context.close()
            browser.close()
        return CrawlResult(snapshot_date=snapshot_date, issues=list(issues.values()))

    def _login(self, page) -> None:
        page.goto(self.config.login_url, wait_until="networkidle")
        page.locator(self.config.username_selector).fill(self.config.username)
        page.locator(self.config.password_selector).fill(self.config.password)
        page.locator(self.config.submit_selector).click()
        page.wait_for_load_state("networkidle")

    def _parse_issue_row(self, row, source_filter: str) -> IssueRecord:
        def safe_text(selector: str) -> str | None:
            locator = row.locator(selector)
            return locator.first.inner_text().strip() if locator.count() else None

        key_locator = row.locator(self.config.issue_key_selector)
        issue_key = key_locator.first.inner_text().strip() if key_locator.count() else ""
        summary = safe_text(self.config.title_selector) or ""
        return IssueRecord(
            issue_key=issue_key,
            summary=summary,
            status=safe_text(self.config.status_selector) or "Unknown",
            assignee=safe_text(self.config.assignee_selector),
            priority=safe_text(self.config.priority_selector),
            updated_at=safe_text(self.config.updated_selector),
            project=issue_key.split("-")[0] if issue_key else None,
            source_filter=source_filter,
        )


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
