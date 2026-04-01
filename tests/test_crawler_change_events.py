from types import SimpleNamespace

from app.crawler import JiraCrawler, iter_snapshot_dates, reconstruct_snapshot_issues
from app.models import IssueChangeEvent
from app.config import JiraConfig
from app.models import IssueRecord


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


def test_to_issue_record_extracts_structured_jira_fields():
    crawler = JiraCrawler(
        JiraConfig(
            base_url="https://jira.example.com",
            access_token="dummy",
            project_filters=[],
            jql="",
            field_mapping={
                "severity": "customfield_10010",
                "root_cause": "customfield_10011",
                "platform_name": "customfield_10012",
                "script_name": "customfield_10013",
            },
        )
    )
    description = {
        "type": "doc",
        "content": [
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Platform Name"}]}]},
                            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Pine"}]}]},
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Expect Result"}]}]},
                            {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "No timeout"}]}]},
                        ],
                    },
                ],
            }
        ],
    }
    fields = SimpleNamespace(
        summary="Timeout in controller recovery",
        status=SimpleNamespace(name="Blocked"),
        issuetype=SimpleNamespace(name="FW Bug"),
        assignee=SimpleNamespace(displayName="Alice"),
        priority=SimpleNamespace(name="Highest"),
        updated="2026-04-01T10:00:00.000+0000",
        created="2026-04-01T09:00:00.000+0000",
        labels=["timeout"],
        components=[SimpleNamespace(name="Recovery")],
        description=description,
        resolution=None,
        fixVersions=[SimpleNamespace(name="1.0.1")],
        versions=[SimpleNamespace(name="1.0.0")],
        comment=SimpleNamespace(comments=[SimpleNamespace(body="Need more logs")]),
        issuelinks=[
            SimpleNamespace(
                type=SimpleNamespace(name="Blocks"),
                outwardIssue=SimpleNamespace(
                    key="SSD-321",
                    fields=SimpleNamespace(summary="Release validation"),
                ),
                inwardIssue=None,
            )
        ],
        customfield_10010="Major",
        customfield_10011="DMA race",
        customfield_10012="Birch",
        customfield_10013="repro_timeout.py",
    )
    issue = SimpleNamespace(key="[SV]SSD-100", fields=fields)

    record = crawler._to_issue_record(issue, "default")

    assert record.issue_type == "FW Bug"
    assert record.severity == "Major"
    assert record.root_cause == "DMA race"
    assert record.fix_versions == ["1.0.1"]
    assert record.affects_versions == ["1.0.0"]
    assert record.blocks_links
    assert record.description_fields["Platform Name"] == "Birch"
    assert record.description_fields["Script Name"] == "repro_timeout.py"
    assert record.description_fields["Expect Result"] == "No timeout"


def test_reconstruct_snapshot_issues_rolls_back_future_status_and_assignee():
    issues = [
        IssueRecord(
            issue_key="[SV]SSD-100",
            summary="Admin queue timeout",
            status="Done",
            team="SV",
            assignee="Alice",
            created_at="2026-04-01T08:00:00.000+0000",
        )
    ]
    events = [
        IssueChangeEvent(
            event_id="1",
            issue_key="[SV]SSD-100",
            changed_at="2026-04-03T09:00:00.000+0000",
            author="Alice",
            field="status",
            from_value="Blocked",
            to_value="Done",
            change_type="closed",
        ),
        IssueChangeEvent(
            event_id="2",
            issue_key="[SV]SSD-100",
            changed_at="2026-04-03T10:00:00.000+0000",
            author="Alice",
            field="assignee",
            from_value="Bob",
            to_value="Alice",
            change_type="assignee_changed",
        ),
    ]

    reconstructed = reconstruct_snapshot_issues(issues, events, "2026-04-02")

    assert len(reconstructed) == 1
    assert reconstructed[0].status == "Blocked"
    assert reconstructed[0].assignee == "Bob"


def test_iter_snapshot_dates_builds_inclusive_range():
    assert iter_snapshot_dates("2026-04-01", "2026-04-03") == [
        "2026-04-01",
        "2026-04-02",
        "2026-04-03",
    ]
