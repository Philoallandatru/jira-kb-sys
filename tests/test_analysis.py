from app.analysis import _fallback_daily_analysis
from app.docs import BM25Index
from app.models import DailyMetrics, DailyReport, IssueRecord, PriorityIssue


def test_offline_fallback_analysis_produces_actions():
    issues = [
        IssueRecord(
            issue_key="SSD-101",
            summary="Admin queue timeout under load",
            status="Blocked",
            priority="High",
            project="SSD",
            description="Timeout after reset recovery",
            labels=["timeout"],
            components=["recovery"],
        )
    ]
    report = DailyReport(
        report_date="2026-03-30",
        generated_at="2026-03-30T00:00:00Z",
        run_id=None,
        metrics=DailyMetrics(total_issues=1, new_issues=1, closed_issues=0, blocked_issues=1, stale_issues=0, status_counts={"Blocked": 1}),
        project_summaries=[],
        priority_issues=[
            PriorityIssue(
                issue_key="SSD-101",
                summary="Admin queue timeout under load",
                status="Blocked",
                assignee=None,
                priority="High",
                change_summary="Status changed from In Progress to Blocked",
            )
        ],
    )
    daily_analysis, issue_analyses = _fallback_daily_analysis(report, BM25Index([]), issues)
    assert daily_analysis.overall_health == "At risk"
    assert issue_analyses
    assert issue_analyses[0].action_needed
