from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from app.config import load_config
from app.docs import BM25Index, DocumentConverter
from app.models import IssueRecord, infer_team_from_issue_key
from app.qa import answer_jira_docs_question, answer_question
from app.repository import Repository


st.set_page_config(page_title="Jira Summary", layout="wide")
config = load_config()
repo = Repository(config.storage.database_path)


def report_payload(report_date: str) -> dict:
    path = Path(config.storage.output_dir) / "daily" / report_date / "report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_uploads(files) -> list[str]:
    saved: list[str] = []
    raw_dir = Path(config.docs.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    for item in files:
        target = raw_dir / item.name
        target.write_bytes(item.getbuffer())
        saved.append(str(target))
    return saved


def rebuild_kb() -> int:
    _, chunks = DocumentConverter(config.docs).build_documents()
    repo.save_doc_chunks(chunks)
    return len(chunks)


def apply_team_filter(issues: list[IssueRecord], team_filter: str | None) -> list[IssueRecord]:
    if not team_filter or team_filter == "All":
        return issues
    normalized = team_filter.upper()
    return [issue for issue in issues if (issue.team or infer_team_from_issue_key(issue.issue_key)) == normalized]


def available_teams(issues: list[IssueRecord]) -> list[str]:
    values = sorted({team for issue in issues for team in [(issue.team or infer_team_from_issue_key(issue.issue_key))] if team})
    return ["All"] + values


st.title("Jira Daily Summary")
dates = repo.list_snapshot_dates()
view = st.sidebar.radio(
    "View",
    ["Dashboard", "Daily Reports", "Issue Explorer", "Knowledge Hits", "Ask Docs", "Ask Jira + Docs", "Manage Knowledge"],
)

if view != "Manage Knowledge" and not dates:
    st.warning("No snapshot data available.")
    st.stop()

selected_date = st.sidebar.selectbox("Report date", dates) if dates else None
issues_for_date = repo.load_snapshot(selected_date) if selected_date else []
default_team = config.reporting.team_filter or "All"
team_filter = st.sidebar.selectbox("Team Filter", available_teams(issues_for_date), index=max(0, available_teams(issues_for_date).index(default_team)) if default_team in available_teams(issues_for_date) else 0) if issues_for_date else default_team
filtered_issues = apply_team_filter(issues_for_date, team_filter)
filtered_issue_keys = {issue.issue_key for issue in filtered_issues}
report = report_payload(selected_date) if selected_date else {}

if view == "Dashboard":
    metrics = report.get("metrics", {})
    cols = st.columns(5)
    for col, label, key in zip(
        cols,
        ["Total", "New", "Closed", "Blocked", "Stale"],
        ["total_issues", "new_issues", "closed_issues", "blocked_issues", "stale_issues"],
    ):
        col.metric(label, metrics.get(key, 0))
    status_counts = metrics.get("status_counts", {})
    if status_counts:
        st.bar_chart(pd.DataFrame.from_dict(status_counts, orient="index", columns=["count"]))
    daily_analysis = report.get("daily_analysis") or {}
    if daily_analysis:
        st.subheader("AI Summary")
        st.write(daily_analysis.get("overall_health", "-"))
        for label in ["top_risks", "suspected_root_causes", "recommended_actions", "watch_items"]:
            st.markdown(f"**{label.replace('_', ' ').title()}**")
            for item in daily_analysis.get(label, []):
                st.write(f"- {item}")

elif view == "Daily Reports":
    report_dir = Path(config.storage.output_dir) / "daily" / selected_date
    for name in ["report.md", "report.html", "report.pdf"]:
        path = report_dir / name
        if path.exists() and name.endswith(".md"):
            st.markdown(path.read_text(encoding="utf-8"))
        elif path.exists():
            st.download_button(f"Download {path.suffix.upper().lstrip('.')}", path.read_bytes(), file_name=path.name)

elif view == "Issue Explorer":
    rows = [issue.to_dict() for issue in filtered_issues]
    analyses = {item.issue_key: item for item in repo.load_issue_analyses(selected_date) if item.issue_key in filtered_issue_keys}
    for row in rows:
        row["team"] = row.get("team") or infer_team_from_issue_key(row.get("issue_key", ""))
        analysis = analyses.get(row["issue_key"])
        row["ai_confidence"] = analysis.confidence if analysis else ""
        row["ai_root_cause"] = analysis.suspected_root_cause if analysis else ""
    df = pd.DataFrame(rows)
    if not df.empty:
        projects = ["All"] + sorted(df["project"].dropna().unique().tolist())
        statuses = ["All"] + sorted(df["status"].dropna().unique().tolist())
        project_filter = st.selectbox("Project", projects)
        status_filter = st.selectbox("Status", statuses)
        if project_filter != "All":
            df = df[df["project"] == project_filter]
        if status_filter != "All":
            df = df[df["status"] == status_filter]
    st.dataframe(df, use_container_width=True)

elif view == "Knowledge Hits":
    for item in repo.load_issue_analyses(selected_date):
        if item.issue_key not in filtered_issue_keys:
            continue
        with st.expander(item.issue_key):
            st.write(item.summary)
            st.write("Root cause:", item.suspected_root_cause)
            for evidence in item.evidence:
                st.write(f"- {evidence}")

elif view == "Ask Docs":
    st.header("Ask Docs")
    st.caption("Query the local knowledge base. If the configured OpenAI-compatible Qwen endpoint is unavailable, the app falls back to retrieval-only answering.")
    question = st.text_area("Question", value="What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?", height=110)
    top_k = st.slider("Retrieved chunks", 1, 10, 5)
    chunks = repo.load_doc_chunks()
    if not chunks:
        st.info("No document chunks found. Build the knowledge base first.")
    elif st.button("Ask", type="primary"):
        result = answer_question(config, BM25Index(chunks), question, top_k=top_k)
        st.write(result.answer)
        st.caption(f"Mode: {result.mode}")
        for idx, citation in enumerate(result.citations, start=1):
            st.markdown(f"**{idx}. {' / '.join(citation.get('section_path', [])) or 'Unknown section'}**")
            st.code(citation.get("quote", ""), language="text")
            st.caption(citation.get("source_path", ""))

elif view == "Ask Jira + Docs":
    st.header("Ask Jira + Docs")
    st.caption("Ask a combined question over the selected day's Jira snapshot and the local knowledge base.")
    question = st.text_area(
        "Question",
        value="Which Jira item is most relevant to NVMe admin queue timeout recovery, and what local spec/design evidence supports it?",
        height=110,
    )
    top_k = st.slider("Retrieved document chunks", 1, 10, 5, key="combined_top_k")
    issue_analyses = [item for item in repo.load_issue_analyses(selected_date) if item.issue_key in filtered_issue_keys]
    daily_analysis = repo.load_daily_analysis(selected_date)
    chunks = repo.load_doc_chunks()
    if not chunks:
        st.info("No document chunks found. Build the knowledge base first.")
    elif not filtered_issues:
        st.info("No Jira snapshot found for the selected date and team filter.")
    elif st.button("Ask Combined", type="primary"):
        result = answer_jira_docs_question(
            config,
            BM25Index(chunks),
            question,
            filtered_issues,
            issue_analyses,
            daily_analysis,
            top_k=top_k,
        )
        st.subheader("Answer")
        st.write(result.answer)
        st.caption(f"Mode: {result.mode}")
        st.subheader("Relevant Jira Context")
        if result.jira_context:
            st.dataframe(pd.DataFrame(result.jira_context), use_container_width=True)
        else:
            st.info("No Jira items were selected as relevant.")
        st.subheader("Document Citations")
        for idx, citation in enumerate(result.doc_citations, start=1):
            st.markdown(f"**{idx}. {' / '.join(citation.get('section_path', [])) or 'Unknown section'}**")
            st.code(citation.get("quote", ""), language="text")
            st.caption(citation.get("source_path", ""))

else:
    st.header("Manage Knowledge")
    files = st.file_uploader(
        "Upload PDF/PPTX/XLSX/DOCX files",
        type=["pdf", "pptx", "xlsx", "xls", "docx"],
        accept_multiple_files=True,
    )
    if files and st.button("Upload Files"):
        saved = save_uploads(files)
        st.success(f"Saved {len(saved)} file(s)")
        for path in saved:
            st.write(path)
    if st.button("Rebuild Knowledge Base", type="primary"):
        st.success(f"Indexed {rebuild_kb()} chunks")
    raw_files = sorted(Path(config.docs.raw_dir).glob("*"))
    if raw_files:
        st.dataframe(
            pd.DataFrame([{"name": path.name, "size_bytes": path.stat().st_size, "path": str(path.resolve())} for path in raw_files]),
            use_container_width=True,
        )
    else:
        st.info("No raw documents found yet.")
