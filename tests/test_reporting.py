from app.config import load_config
from app.models import IssueDelta, IssueRecord
from app.reporting import build_daily_report


def test_build_daily_report_marks_priority_issue(tmp_path):
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
  base_url: "http://localhost:8000/v1"
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
        IssueRecord(issue_key="SSD-1", summary="Timeout in admin queue", status="In Progress", priority="High", project="SSD"),
        IssueRecord(issue_key="SSD-2", summary="Normal task", status="Done", priority="Low", project="SSD"),
    ]
    deltas = [IssueDelta(issue_key="SSD-1", change_type="status_changed", details="Status changed from Open to In Progress")]
    report = build_daily_report("2026-03-30", issues, deltas, set(), config)
    assert report.metrics.total_issues == 2
    assert report.priority_issues[0].issue_key == "SSD-1"
