from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from app.config import load_config
from app.docs import BM25Index, DocumentConverter
from app.qa import answer_question
from app.repository import Repository

st.set_page_config(page_title="Jira Summary", layout="wide")
config = load_config()
repo = Repository(config.storage.database_path)

def report_payload(d: str) -> dict:
    p = Path(config.storage.output_dir) / "daily" / d / "report.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def save_uploads(files) -> list[str]:
    out = []
    raw = Path(config.docs.raw_dir)
    raw.mkdir(parents=True, exist_ok=True)
    for f in files:
        t = raw / f.name
        t.write_bytes(f.getbuffer())
        out.append(str(t))
    return out

def rebuild_kb() -> int:
    _, chunks = DocumentConverter(config.docs).build_documents()
    repo.save_doc_chunks(chunks)
    return len(chunks)

st.title("Jira Daily Summary")
dates = repo.list_snapshot_dates()
view = st.sidebar.radio("View", ["Dashboard", "Daily Reports", "Issue Explorer", "Knowledge Hits", "Ask Docs", "Manage Knowledge"])
if view != "Manage Knowledge" and not dates:
    st.warning("No snapshot data available.")
    st.stop()
date_value = st.sidebar.selectbox("Report date", dates) if dates else None
report = report_payload(date_value) if date_value else {}

if view == "Dashboard":
    m = report.get("metrics", {})
    cols = st.columns(5)
    for col, label, key in zip(cols, ["Total", "New", "Closed", "Blocked", "Stale"], ["total_issues", "new_issues", "closed_issues", "blocked_issues", "stale_issues"]):
        col.metric(label, m.get(key, 0))
    sc = m.get("status_counts", {})
    if sc:
        st.bar_chart(pd.DataFrame.from_dict(sc, orient="index", columns=["count"]))
    da = report.get("daily_analysis") or {}
    if da:
        st.subheader("AI Summary")
        st.write(da.get("overall_health", "-"))
        for label in ["top_risks", "suspected_root_causes", "recommended_actions", "watch_items"]:
            st.markdown(f"**{label.replace('_', ' ').title()}**")
            for item in da.get(label, []):
                st.write(f"- {item}")
elif view == "Daily Reports":
    rd = Path(config.storage.output_dir) / "daily" / date_value
    for name in ["report.md", "report.html", "report.pdf"]:
        p = rd / name
        if p.exists() and name.endswith(".md"):
            st.markdown(p.read_text(encoding="utf-8"))
        elif p.exists():
            st.download_button(f"Download {p.suffix.upper().lstrip('.')}" , p.read_bytes(), file_name=p.name)
elif view == "Issue Explorer":
    rows = [x.to_dict() for x in repo.load_snapshot(date_value)]
    amap = {x.issue_key: x for x in repo.load_issue_analyses(date_value)}
    for row in rows:
        a = amap.get(row["issue_key"])
        row["ai_confidence"] = a.confidence if a else ""
        row["ai_root_cause"] = a.suspected_root_cause if a else ""
    df = pd.DataFrame(rows)
    if not df.empty:
        pj = st.selectbox("Project", ["All"] + sorted(df["project"].dropna().unique().tolist()))
        stt = st.selectbox("Status", ["All"] + sorted(df["status"].dropna().unique().tolist()))
        if pj != "All":
            df = df[df["project"] == pj]
        if stt != "All":
            df = df[df["status"] == stt]
    st.dataframe(df, use_container_width=True)
elif view == "Knowledge Hits":
    for item in repo.load_issue_analyses(date_value):
        with st.expander(item.issue_key):
            st.write(item.summary)
            st.write("Root cause:", item.suspected_root_cause)
            for evidence in item.evidence:
                st.write(f"- {evidence}")
elif view == "Ask Docs":
    st.header("Ask Docs")
    st.caption("Query the local knowledge base. If the configured OpenAI-compatible Qwen endpoint is unavailable, the app falls back to retrieval-only answering.")
    q = st.text_area("Question", value="What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?", height=110)
    top_k = st.slider("Retrieved chunks", 1, 10, 5)
    chunks = repo.load_doc_chunks()
    if not chunks:
        st.info("No document chunks found. Build the knowledge base first.")
    elif st.button("Ask", type="primary"):
        r = answer_question(config, BM25Index(chunks), q, top_k=top_k)
        st.write(r.answer)
        st.caption(f"Mode: {r.mode}")
        for i, c in enumerate(r.citations, start=1):
            st.markdown(f"**{i}. {' / '.join(c.get('section_path', [])) or 'Unknown section'}**")
            st.code(c.get("quote", ""), language="text")
            st.caption(c.get("source_path", ""))
else:
    st.header("Manage Knowledge")
    files = st.file_uploader("Upload PDF/PPTX/XLSX/DOCX files", type=["pdf", "pptx", "xlsx", "xls", "docx"], accept_multiple_files=True)
    if files and st.button("Upload Files"):
        saved = save_uploads(files)
        st.success(f"Saved {len(saved)} file(s)")
        for p in saved:
            st.write(p)
    if st.button("Rebuild Knowledge Base", type="primary"):
        st.success(f"Indexed {rebuild_kb()} chunks")
    raw = sorted(Path(config.docs.raw_dir).glob("*"))
    if raw:
        st.dataframe(pd.DataFrame([{"name": p.name, "size_bytes": p.stat().st_size, "path": str(p.resolve())} for p in raw]), use_container_width=True)
    else:
        st.info("No raw documents found yet.")
