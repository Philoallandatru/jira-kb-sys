from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app.config import load_config
from app.docs import BM25Index, DocumentConverter
from app.management import build_management_summary, render_management_markdown
from app.models import IssueRecord, ManagementSummaryRequest, infer_team_from_issue_key
from app.qa import answer_jira_docs_question, answer_question
from app.reporting import build_daily_report, render_markdown
from app.repository import Repository


st.set_page_config(page_title="Jira Summary", layout="wide")
config = load_config()
repo = Repository(config.storage.database_path)


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --paper: #f3eadb;
          --ink: #1d1b19;
          --rust: #a34b2a;
          --olive: #596646;
          --steel: #5c6d7a;
          --panel: rgba(255, 250, 240, 0.78);
          --line: rgba(29, 27, 25, 0.18);
        }
        .stApp {
          background:
            radial-gradient(circle at top left, rgba(163, 75, 42, 0.18), transparent 28%),
            radial-gradient(circle at top right, rgba(89, 102, 70, 0.18), transparent 26%),
            linear-gradient(180deg, #efe2cc 0%, #f8f1e7 48%, #efe5d6 100%);
          color: var(--ink);
        }
        .block-container {
          padding-top: 1.4rem;
          max-width: 1400px;
        }
        h1, h2, h3 {
          font-family: Georgia, "Times New Roman", serif !important;
          letter-spacing: 0.02em;
          color: #231f1a;
        }
        section[data-testid="stSidebar"] {
          background: linear-gradient(180deg, rgba(35, 31, 26, 0.92), rgba(51, 42, 34, 0.96));
          border-right: 1px solid rgba(255,255,255,0.08);
        }
        section[data-testid="stSidebar"] * {
          color: #f5ead8 !important;
        }
        div[data-testid="stMetric"] {
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 14px;
          box-shadow: 0 10px 24px rgba(48, 35, 27, 0.08);
          padding: 0.35rem 0.5rem;
        }
        .retro-hero {
          background: linear-gradient(135deg, rgba(255,250,240,0.88), rgba(240,226,206,0.84));
          border: 1px solid var(--line);
          border-radius: 18px;
          padding: 1.25rem 1.5rem;
          box-shadow: 0 18px 40px rgba(56, 40, 28, 0.08);
          margin-bottom: 1rem;
        }
        .retro-tag {
          display: inline-block;
          border: 1px solid rgba(35,31,26,0.22);
          background: rgba(163, 75, 42, 0.08);
          color: var(--rust);
          border-radius: 999px;
          padding: 0.18rem 0.65rem;
          margin-right: 0.45rem;
          font-size: 0.82rem;
        }
        .retro-panel {
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 16px;
          padding: 1rem 1.1rem;
          box-shadow: 0 12px 28px rgba(56, 40, 28, 0.06);
        }
        .stButton button {
          border-radius: 999px;
          border: 1px solid rgba(35,31,26,0.18);
          background: linear-gradient(180deg, #b85f38, #934121);
          color: #fff8f1;
          font-weight: 600;
        }
        .stDownloadButton button {
          border-radius: 999px;
        }
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        textarea {
          background: rgba(255, 249, 240, 0.92) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def issue_analysis_dict(report_date: str, issue_keys: set[str]) -> dict[str, dict]:
    return {
        item.issue_key: item.to_dict()
        for item in repo.load_issue_analyses(report_date)
        if item.issue_key in issue_keys
    }


def build_filtered_view(report_date: str, issues: list[IssueRecord], team_filter: str) -> tuple[object, dict[str, dict], object | None]:
    issue_keys = {issue.issue_key for issue in issues}
    deltas = [item for item in repo.load_deltas(report_date) if item.issue_key in issue_keys]
    stale_keys = repo.compute_stale_issue_keys(report_date, config.reporting.stale_days) & issue_keys
    report_obj = build_daily_report(report_date, issues, deltas, stale_keys, config)
    issue_analyses = issue_analysis_dict(report_date, issue_keys)
    configured_team = config.reporting.team_filter or "All"
    daily_analysis = repo.load_daily_analysis(report_date) if team_filter == configured_team else None
    return report_obj, issue_analyses, daily_analysis


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


def hero() -> None:
    st.markdown(
        """
        <div class="retro-hero">
          <div class="retro-tag">Vintage Ops</div>
          <div class="retro-tag">Modern AI</div>
          <div class="retro-tag">Jira · Spec · Policy</div>
          <h1 style="margin:0.6rem 0 0.35rem 0;">Jira Summary Control Deck</h1>
          <p style="margin:0;color:#54483f;">
            一个偏复古现代感的控制台，用来查看 Jira 变化、生成日报、问答本地知识库，并为管理层输出结构化摘要。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


inject_theme()
hero()
dates = repo.list_snapshot_dates()
view = st.sidebar.radio(
    "View",
    ["Dashboard", "Daily Reports", "Management Summary", "Issue Explorer", "Knowledge Hits", "Ask Docs", "Ask Jira + Docs", "Manage Knowledge"],
)

if view != "Manage Knowledge" and not dates:
    st.warning("No snapshot data available.")
    st.stop()

selected_date = st.sidebar.selectbox("Report date", dates) if dates else None
issues_for_date = repo.load_snapshot(selected_date) if selected_date else []
default_team = config.reporting.team_filter or "All"
team_options = available_teams(issues_for_date) if issues_for_date else ["All"]
team_filter = st.sidebar.selectbox(
    "Team Filter",
    team_options,
    index=max(0, team_options.index(default_team)) if default_team in team_options else 0,
)
filtered_issues = apply_team_filter(issues_for_date, team_filter)
filtered_issue_keys = {issue.issue_key for issue in filtered_issues}
filtered_report, filtered_issue_analyses, filtered_daily_analysis = build_filtered_view(selected_date, filtered_issues, team_filter) if selected_date else (None, {}, None)

if view == "Dashboard":
    metrics = filtered_report.metrics.to_dict() if filtered_report else {}
    cols = st.columns(5)
    for col, label, key in zip(
        cols,
        ["Total", "New", "Closed", "Blocked", "Stale"],
        ["total_issues", "new_issues", "closed_issues", "blocked_issues", "stale_issues"],
    ):
        col.metric(label, metrics.get(key, 0))
    status_counts = metrics.get("status_counts", {})
    left, right = st.columns([1.2, 1])
    with left:
        with st.container(border=True):
            st.subheader("Status Counts")
            if status_counts:
                st.bar_chart(pd.DataFrame.from_dict(status_counts, orient="index", columns=["count"]))
            else:
                st.info("当前没有可展示的状态分布。")
    with right:
        with st.container(border=True):
            st.subheader("AI Summary")
            if filtered_daily_analysis:
                st.write(filtered_daily_analysis.overall_health)
                for label in ["top_risks", "suspected_root_causes", "recommended_actions", "watch_items"]:
                    st.markdown(f"**{label.replace('_', ' ').title()}**")
                    for item in getattr(filtered_daily_analysis, label):
                        st.write(f"- {item}")
            elif team_filter != (config.reporting.team_filter or "All"):
                st.info("当前 Dashboard 指标已按页面团队筛选实时重算。AI Summary 仍只展示与默认团队一致的已落库分析结果。")
            else:
                st.info("暂无 AI Summary。")

elif view == "Daily Reports":
    report_dir = Path(config.storage.output_dir) / "daily" / selected_date
    if filtered_report:
        st.markdown(render_markdown(filtered_report, filtered_daily_analysis, filtered_issue_analyses))
    if team_filter != "All":
        st.caption(f"当前页面内容为团队筛选 `{team_filter}` 的实时视图；下方下载文件仍是上次生成的原始日报产物。")
    action_cols = st.columns(3)
    for idx, name in enumerate(["report.md", "report.html", "report.pdf"]):
        path = report_dir / name
        with action_cols[idx]:
            if path.exists() and name.endswith(".md"):
                with st.expander("Stored Markdown Artifact", expanded=False):
                    st.code(path.read_text(encoding="utf-8"), language="markdown")
            elif path.exists():
                st.download_button(f"Download {path.suffix.upper().lstrip('.')}", path.read_bytes(), file_name=path.name)

elif view == "Management Summary":
    st.header("Management Summary")
    st.caption("面向管理层的结构化摘要，聚焦最近更新过的 Jira、风险、趋势、协作效率和闭环质量。")
    c1, c2 = st.columns(2)
    with c1:
        default_date = pd.to_datetime(selected_date).date() if selected_date else pd.Timestamp.today().date()
        date_from = st.date_input("Date From", value=default_date)
    with c2:
        date_to = st.date_input("Date To", value=default_date)
    status_options = sorted({issue.status for issue in issues_for_date if issue.status})
    status_filter = st.multiselect("Jira Status", options=status_options, default=[])
    if st.button("Generate Management Summary", type="primary"):
        request = ManagementSummaryRequest(
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            team=None if team_filter == "All" else team_filter,
            jira_status=status_filter,
        )
        result = build_management_summary(config, repo, request)
        st.markdown(render_management_markdown(result))
        info_left, info_right = st.columns(2)
        with info_left:
            st.subheader("Referenced Issue Keys")
            st.write(", ".join(result.referenced_issue_keys) if result.referenced_issue_keys else "-")
        with info_right:
            st.subheader("Referenced Metrics")
            st.json(result.referenced_metrics)

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
    st.caption("查询本地知识库。若本地 OpenAI-compatible Qwen 服务不可用，则自动退回检索式回答。")
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
    st.caption("针对选定日期的 Jira 快照和本地知识库做联合问答。")
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
