from types import SimpleNamespace

from app.config import JiraConfig
from app.crawler import JiraCrawler


def test_crawler_uses_report_department_as_team():
    crawler = JiraCrawler(JiraConfig(base_url="https://jira.example.com", access_token="token"))
    issue = SimpleNamespace(
        key="[SV]SSD-101",
        fields={
            "summary": "Queue timeout",
            "status": {"name": "Open"},
            "report_department": "FW Platform",
        },
    )

    record = crawler._to_issue_record(issue, "default")

    assert record.team == "FW Platform"
    assert record.report_department == "FW Platform"


def test_change_events_use_report_department_as_team_after():
    crawler = JiraCrawler(JiraConfig(base_url="https://jira.example.com", access_token="token"))
    issue = SimpleNamespace(
        key="[DV]SSD-202",
        fields={"report_department": "Validation"},
        changelog=SimpleNamespace(
            histories=[
                SimpleNamespace(
                    id="1",
                    created="2026-04-03T09:00:00+0000",
                    author=SimpleNamespace(displayName="Codex"),
                    items=[SimpleNamespace(field="status", fromString="Open", toString="Blocked")],
                )
            ]
        ),
    )

    events = crawler._extract_change_events(issue)

    assert len(events) == 1
    assert events[0].team_after == "Validation"
