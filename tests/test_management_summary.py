from app.management import _build_metrics
from app.models import IssueDelta, IssueRecord


def test_build_management_metrics_counts_core_signals():
    issues = [
        IssueRecord(issue_key="[SV]SSD-1", summary="Timeout", status="Blocked", team="SV", priority="High", assignee="Alice"),
        IssueRecord(issue_key="[DV]SSD-2", summary="Recovery", status="In Progress", team="DV", priority="Low", assignee=None),
    ]
    deltas = [
        IssueDelta(issue_key="[SV]SSD-1", change_type="status_changed", details="Status changed from Open to Blocked"),
        IssueDelta(issue_key="[SV]SSD-1", change_type="assignee_changed", details="Assignee changed from Bob to Alice"),
        IssueDelta(issue_key="[DV]SSD-2", change_type="closed", details="Status changed from In Progress to Closed"),
        IssueDelta(issue_key="[DV]SSD-2", change_type="reopened", details="Status changed from Closed to In Progress"),
    ]
    metrics = _build_metrics(issues, deltas)
    assert metrics.updated_issue_count == 2
    assert metrics.status_progress_count == 1
    assert metrics.closed_count == 1
    assert metrics.reopened_count == 1
    assert metrics.assignee_change_count == 1
    assert metrics.blocked_count == 1
    assert metrics.high_priority_open_count == 1
    assert metrics.issues_without_owner == 1
