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
  login_url: "https://jira.example.com/login"
  username: ""
  password: ""
  project_filters: []
  auth_state_path: "./data/jira_auth.json"
  list_selector: "table tbody tr"
  detail_link_selector: ""
  username_selector: "input[name='username']"
  password_selector: "input[name='password']"
  submit_selector: "button[type='submit']"
  issue_key_selector: "td"
  title_selector: "td"
  status_selector: "td"
  assignee_selector: "td"
  priority_selector: "td"
  updated_selector: "td"
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
        IssueRecord(issue_key="SSD-101", summary="Admin queue timeout under load", status="Blocked", priority="High", project="SSD"),
        IssueRecord(issue_key="SSD-102", summary="Telemetry mismatch", status="Open", priority="Low", project="SSD"),
    ]
    analyses = [
        IssueAIAnalysis(
            report_date="2026-03-30",
            issue_key="SSD-101",
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
    result = answer_jira_docs_question(config, BM25Index(chunks), "Which Jira item relates to admin queue timeout?", issues, analyses, daily)
    assert result.mode == "fallback"
    assert result.jira_context
    assert result.jira_context[0]["issue_key"] == "SSD-101"
    assert result.doc_citations
