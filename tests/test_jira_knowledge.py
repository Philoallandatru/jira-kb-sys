from app.config import DocsConfig
from app.jira_knowledge import build_jira_chunks, filter_product_doc_chunks
from app.models import DailyAIAnalysis, DocChunk, IssueAIAnalysis, IssueRecord
from app.repository import Repository


def test_build_jira_chunks_emits_issue_issue_analysis_and_daily_analysis(tmp_path):
    repo = Repository(str(tmp_path / "test.db"))
    repo.save_daily_snapshot(
        "2026-04-01",
        [
            IssueRecord(
                issue_key="[SV]SSD-123",
                summary="Admin queue timeout under reset",
                status="Blocked",
                team="SV",
                priority="High",
                description="Controller sometimes times out during recovery.",
                issue_type="FW Bug",
                severity="Major",
                root_cause="Queue ordering not restored",
                description_fields={"Platform Name": "Pine", "Script Name": "repro.py"},
            )
        ],
    )
    repo.save_issue_analyses(
        [
            IssueAIAnalysis(
                report_date="2026-04-01",
                issue_key="[SV]SSD-123",
                summary="Admin queue timeout under reset",
                suspected_root_cause="Queue ordering is not restored after reset.",
                evidence=["NVMe reset guidance"],
                action_needed=["Collect reset and timeout logs"],
                confidence="medium",
                raw_response="fallback",
            )
        ]
    )
    repo.save_daily_analysis(
        DailyAIAnalysis(
            report_date="2026-04-01",
            overall_health="At risk",
            top_risks=["Blocked recovery path"],
            suspected_root_causes=["Queue ordering"],
            recommended_actions=["Collect logs"],
            watch_items=["Blocked issues: 1"],
            raw_response="fallback",
        )
    )

    chunks = build_jira_chunks(
        repo,
        DocsConfig(
            raw_dir=str(tmp_path / "raw"),
            markdown_dir=str(tmp_path / "markdown"),
            chunks_dir=str(tmp_path / "chunks"),
            supported_extensions=[".md"],
        ),
    )
    source_types = {chunk.source_type for chunk in chunks}

    assert "jira_issue" in source_types
    assert "jira_issue_analysis" in source_types
    assert "jira_daily_analysis" in source_types
    assert any("pine" in chunk.tags for chunk in chunks)


def test_filter_product_doc_chunks_excludes_jira_prefix():
    chunks = [
        DocChunk(
            chunk_id="doc-1",
            source_path="/docs/spec.md",
            source_type="md",
            doc_title="Spec",
            section_path=["Intro"],
            page_or_sheet=None,
            content="spec chunk",
            tags=["spec"],
            updated_at="2026-04-01T00:00:00Z",
        ),
        DocChunk(
            chunk_id="jira-1",
            source_path="jira://snapshot/2026-04-01/SSD-1",
            source_type="jira_issue",
            doc_title="SSD-1",
            section_path=["Metadata"],
            page_or_sheet=None,
            content="jira chunk",
            tags=["jira"],
            updated_at="2026-04-01T00:00:00Z",
        ),
    ]

    filtered = filter_product_doc_chunks(chunks)

    assert len(filtered) == 1
    assert filtered[0].source_type == "md"
