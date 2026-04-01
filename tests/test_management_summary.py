from app.management import _build_metrics, _fallback_management_summary, render_management_markdown
from app.models import IssueDelta, IssueRecord, ManagementSummaryRequest


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


def test_render_management_markdown_uses_readable_labels():
    issues = [IssueRecord(issue_key="[SV]SSD-1", summary="Timeout", status="Blocked", team="SV", priority="High", assignee="Alice")]
    deltas = [IssueDelta(issue_key="[SV]SSD-1", change_type="status_changed", details="Status changed from Open to Blocked")]
    metrics = _build_metrics(issues, deltas)
    result = _fallback_management_summary(
        run_id=1,
        request=ManagementSummaryRequest(date_from="2026-04-01", date_to="2026-04-02"),
        metrics=metrics,
        issues=issues,
        deltas=deltas,
        issue_analyses={},
    )

    markdown = render_management_markdown(result)

    assert "# Jira 管理层摘要" in markdown
    assert "## 核心指标" in markdown
    assert "## 当前风险与阻塞" in markdown
    assert "## 数据不足" in markdown
