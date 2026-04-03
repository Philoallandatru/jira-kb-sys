from app.issue_details import _fallback_issue_deep_analysis
from app.models import DocChunk, IssueAIAnalysis, IssueRecord
from app.docs import SearchHit


def test_fallback_issue_deep_analysis_groups_spec_and_policy_hits():
    issue = IssueRecord(
        issue_key="[SV]SSD-200",
        summary="Admin queue timeout after reset",
        status="Blocked",
        team="SV",
        priority="High",
        description="Reset recovery path sometimes times out.",
        assignee=None,
    )
    hits = [
        SearchHit(
            chunk=DocChunk(
                chunk_id="spec-1",
                source_path="/docs/spec/nvme.md",
                source_type="md",
                doc_title="NVMe Spec",
                section_path=["Reset Behavior"],
                page_or_sheet=None,
                content="The controller should restore queue ordering after reset.",
                tags=["spec"],
                updated_at="2026-04-01T00:00:00Z",
            ),
            score=9.1,
        ),
        SearchHit(
            chunk=DocChunk(
                chunk_id="policy-1",
                source_path="/docs/policy/recovery.md",
                source_type="md",
                doc_title="Recovery Policy",
                section_path=["Owner Rules"],
                page_or_sheet=None,
                content="High-risk recovery changes require clear owner and rollback criteria.",
                tags=["policy"],
                updated_at="2026-04-01T00:00:00Z",
            ),
            score=8.7,
        ),
    ]
    cached_analysis = IssueAIAnalysis(
        report_date="2026-04-01",
        issue_key=issue.issue_key,
        summary=issue.summary,
        suspected_root_cause="Queue ordering may not be restored after reset.",
        evidence=["NVMe Spec / Reset Behavior"],
        action_needed=["Collect timeout logs around reset recovery."],
        confidence="medium",
        raw_response="fallback",
    )

    result = _fallback_issue_deep_analysis(issue, hits, [], cached_analysis)

    assert result.spec_relations
    assert result.policy_relations
    assert result.next_actions
    assert result.open_questions
    assert result.citations
    assert len(result.open_questions) >= 1


def test_fallback_issue_deep_analysis_exposes_comment_insights():
    issue = IssueRecord(
        issue_key="SSD-301",
        summary="Controller hang during smoke test",
        status="Blocked",
        team="FW",
        comments=[
            "风险：当前版本在回归阶段仍会 timeout，先不要关闭。",
            "行动：Owner 今天补日志，明天给结论。",
        ],
    )

    result = _fallback_issue_deep_analysis(issue, [], [], None)

    assert result.comment_summary.startswith("共整理")
    assert any("风险" in item or "timeout" in item for item in result.comment_risks_blockers)
    assert any("行动" in item or "结论" in item for item in result.comment_actions_decisions)
