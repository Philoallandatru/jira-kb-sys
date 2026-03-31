from types import SimpleNamespace

from app.crawler import JiraCrawler
from app.models import IssueChangeEvent
from app.config import JiraConfig


def test_extract_change_events_maps_status_and_assignee_changes():
    crawler = JiraCrawler(
        JiraConfig(
            base_url="https://jira.example.com",
            access_token="dummy",
            project_filters=[],
            jql="",
        )
    )
    issue = SimpleNamespace(
        key="[SV]SSD-100",
        changelog=SimpleNamespace(
            histories=[
                SimpleNamespace(
                    id="1",
                    created="2026-04-01T10:00:00.000+0000",
                    author=SimpleNamespace(displayName="Alice"),
                    items=[
                        SimpleNamespace(field="status", fromString="Open", toString="Blocked"),
                        SimpleNamespace(field="assignee", fromString="Bob", toString="Alice"),
                    ],
                )
            ]
        ),
    )

    events = crawler._extract_change_events(issue)

    assert len(events) == 2
    status_event = next(event for event in events if event.field == "status")
    assignee_event = next(event for event in events if event.field == "assignee")
    assert isinstance(status_event, IssueChangeEvent)
    assert status_event.change_type == "status_changed"
    assert assignee_event.change_type == "assignee_changed"
