from app.models import DailyAIAnalysis, IssueAIAnalysis, IssueRecord, DocChunk
from app.qa import answer_jira_docs_question
from app.docs import BM25Index
from app.config import load_config


def test_combined_qa_fallback_selects_relevant_issue(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
jira:
  base_url: "https://jira.example.com"
  access_token: "dummy-token"
  project_filters: []
  jql: "project = SSD"
  max_results: 50
docs:
  raw_dir: "./data/raw_docs"
  markdown_dir: "./data/markdown"
  chunks_dir: "./data/chunks"
storage:
  database_path: "./data/test.db"
  output_dir: "./output"
llm:
  base_url: "http://localhost:65535/v1"
  api_key: "dummy"
  model: "qwen"
reporting:
  stale_days: 7
  risk_keywords: ["timeout"]
  top_issue_limit: 20
""",
        encoding="utf-8",
    )
    config = load_config(str(config_path))
    issues = [
        IssueRecord(issue_key="[SV]SSD-101", summary="Admin queue timeout under load", status="Blocked", team="SV", priority="High", project="SSD"),
        IssueRecord(issue_key="[DV]SSD-102", summary="Telemetry mismatch", status="Open", team="DV", priority="Low", project="SSD"),
    ]
    analyses = [
        IssueAIAnalysis(
            report_date="2026-03-30",
            issue_key="[SV]SSD-101",
            summary="Admin queue timeout under load",
            suspected_root_cause="Queue head tail synchronization issue",
            evidence=["NVMe Admin Queue Recovery Notes"],
            action_needed=["Collect timeout logs"],
            confidence="medium",
            raw_response="offline",
        )
    ]
    daily = DailyAIAnalysis(
        report_date="2026-03-30",
        overall_health="At risk",
        top_risks=["SSD-101 blocked"],
        suspected_root_causes=["Queue synchronization"],
        recommended_actions=["Collect logs"],
        watch_items=["Blocked issues: 1"],
        raw_response="offline",
    )
    chunks = [
        DocChunk(
            chunk_id="doc-1",
            source_path="/tmp/nvme.md",
            source_type="md",
            doc_title="NVMe Notes",
            section_path=["5 Admin Command Set", "5.2 Memory-Based Transport Admin Commands (PCIe)"],
            page_or_sheet=None,
            content="Admin queue timeout recovery requires checking queue head tail synchronization and reset ordering.",
            tags=["nvme", "timeout", "admin-queue"],
            updated_at="2026-03-30T00:00:00Z",
        )
    ]
    result = answer_jira_docs_question(
        config,
        BM25Index(chunks),
        BM25Index([]),
        "Which Jira item relates to admin queue timeout?",
        issues,
        analyses,
        daily,
    )
    assert result.mode == "fallback"
    assert result.jira_context
    assert result.jira_context[0]["issue_key"] == "[SV]SSD-101"
    assert result.jira_context[0]["team"] == "SV"
    assert result.doc_citations


def test_combined_qa_can_retrieve_jira_chunks(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
jira:
  base_url: "https://jira.example.com"
  access_token: "dummy-token"
  project_filters: []
  jql: "project = SSD"
  max_results: 50
docs:
  raw_dir: "./data/raw_docs"
  markdown_dir: "./data/markdown"
  chunks_dir: "./data/chunks"
storage:
  database_path: "./data/test.db"
  output_dir: "./output"
llm:
  base_url: "http://localhost:65535/v1"
  api_key: "dummy"
  model: "qwen"
reporting:
  stale_days: 7
  risk_keywords: ["timeout"]
  top_issue_limit: 20
""",
        encoding="utf-8",
    )
    config = load_config(str(config_path))
    issues = [
        IssueRecord(issue_key="[SV]SSD-101", summary="Admin queue timeout under load", status="Blocked", team="SV", priority="High", project="SSD"),
    ]
    analyses = []
    jira_chunks = [
        DocChunk(
            chunk_id="jira-1",
            source_path="jira://snapshot/2026-03-30/[SV]SSD-101",
            source_type="jira_issue",
            doc_title="[SV]SSD-101 snapshot",
            section_path=["Summary"],
            page_or_sheet=None,
            content="Admin queue timeout under load is currently blocked by missing reset ordering validation.",
            tags=["jira", "timeout", "blocked"],
            updated_at="2026-03-30T00:00:00Z",
        )
    ]
    result = answer_jira_docs_question(
        config,
        BM25Index([]),
        BM25Index(jira_chunks),
        "Which Jira issue is blocked by reset ordering validation?",
        issues,
        analyses,
        None,
    )
    assert result.mode == "fallback"
    assert result.jira_context
    assert result.jira_context[0]["issue_key"] == "[SV]SSD-101"
    assert result.doc_citations
    assert result.doc_citations[0]["source_path"].startswith("jira://")
