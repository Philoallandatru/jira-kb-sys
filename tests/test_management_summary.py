from app.config import load_config
from app.management import _build_metrics, render_management_pdf
from app.models import IssueDelta, IssueRecord, ManagementSummaryMetrics, ManagementSummaryRequest, ManagementSummaryResult


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


def test_render_management_pdf_returns_false_when_native_weasyprint_libs_missing(monkeypatch, tmp_path):
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
    load_config(str(config_path))
    result = ManagementSummaryResult(
        summary_id=1,
        generated_at="2026-04-03T00:00:00Z",
        request=ManagementSummaryRequest(date_from="2026-04-02", date_to="2026-04-03"),
        metrics=ManagementSummaryMetrics(
            updated_issue_count=1,
            status_progress_count=0,
            closed_count=0,
            reopened_count=0,
            assignee_change_count=0,
            blocked_count=0,
            high_priority_open_count=1,
            team_distribution={"SV": 1},
            status_distribution={"Open": 1},
            issue_type_distribution={"Bug": 1},
            severity_distribution={"High": 1},
            root_cause_distribution={"UNKNOWN": 1},
            report_department_distribution={"SV": 1},
            component_distribution={"fw": 1},
            issues_without_owner=0,
            issues_without_root_cause=1,
            issues_without_fix_version=1,
            issues_without_repro_context=1,
            referenced_issue_keys=["SSD-1"],
        ),
        latest_progress_overview=["One issue updated."],
        key_recent_changes=["SSD-1 moved to Open."],
        current_risks_and_blockers=["No active blocker."],
        root_cause_and_pattern_observations=["Root cause not yet confirmed."],
        recommended_management_actions=["Track reproduction quality."],
        data_gaps=["Need fix version."],
        referenced_issue_keys=["SSD-1"],
        referenced_metrics={"updated_issue_count": 1},
        raw_response="{}",
    )

    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "weasyprint":
            raise OSError("missing gtk runtime")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    pdf_written = render_management_pdf(result, tmp_path / "summary.html", tmp_path / "summary.pdf")
    assert pdf_written is False
    assert (tmp_path / "summary.html").exists()
