from app.config import load_config
from app.models import DocChunk, MarkdownDocument
from app.docs import chunk_markdown
from app.qa import answer_question
from app.retrieval import build_retriever
from app.retrieval.query_planner import build_query_plan, QueryType
from app.repository import Repository


def test_chunk_markdown_builds_contextual_fields():
    document = MarkdownDocument(
        document_id="confluence-ssd-42",
        source_path="https://confluence.example.com/pages/viewpage.action?pageId=42",
        source_type="confluence_page",
        title="SSD FW Tuning Guide",
        markdown_path="/tmp/ssd-fw.md",
        content="# Known Regressions\n\n4K random write drops under FW 1.0.7.\n",
        updated_at="2026-03-28T00:00:00Z",
        metadata={
            "source_id": "confluence:42",
            "space_key": "SSD",
            "page_id": "42",
            "page_title": "SSD FW Tuning Guide",
            "ancestor_titles": ["Firmware", "Performance", "GC"],
            "labels": ["perf", "gc", "fw-1.0.7"],
            "comment_snippets": ["Observed during nightly regression"],
        },
    )

    chunks = list(chunk_markdown(document, max_chunk_chars=500, overlap_chars=50))
    assert chunks
    first = chunks[0]
    assert first.source_id == "confluence:42"
    assert first.space_key == "SSD"
    assert first.page_id == "42"
    assert "Page: SSD FW Tuning Guide" in first.context_prefix
    assert "Known Regressions" in first.retrieval_text
    assert "1.0.7" in " ".join(first.exact_terms)


def test_query_planner_detects_identifier_heavy(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
jira:
  base_url: "https://jira.example.com"
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
""",
        encoding="utf-8",
    )
    config = load_config(str(config_path))
    plan = build_query_plan(config, "Which issue references [SV]SSD-101 and FW 1.0.7?")
    assert plan.query_type == QueryType.IDENTIFIER_HEAVY
    assert "jira_issue" in plan.force_include_source_types


def test_hybrid_retriever_prefers_exact_identifier_match(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
jira:
  base_url: "https://jira.example.com"
docs:
  raw_dir: "./data/raw_docs"
  markdown_dir: "./data/markdown"
  chunks_dir: "./data/chunks"
retrieval:
  index_dir: "./data/retrieval"
storage:
  database_path: "./data/test.db"
  output_dir: "./output"
llm:
  base_url: "http://localhost:8000/v1"
  api_key: "dummy"
  model: "qwen"
reporting:
  stale_days: 7
""",
        encoding="utf-8",
    )
    config = load_config(str(config_path))
    chunks = [
        DocChunk(
            chunk_id="jira-1",
            source_path="jira://snapshot/2026-03-30/[SV]SSD-101",
            source_type="jira_issue",
            doc_title="[SV]SSD-101 snapshot",
            page_or_sheet=None,
            updated_at="2026-03-30T00:00:00Z",
            source_id="jira:[SV]SSD-101",
            page_title="[SV]SSD-101 snapshot",
            heading_path=["Summary"],
            section_path=["Summary"],
            content="Reset ordering validation blocks this issue.",
            raw_text="Reset ordering validation blocks this issue.",
            context_prefix="Page: [SV]SSD-101 snapshot\nSection: Summary",
            retrieval_text="Page: [SV]SSD-101 snapshot\nSection: Summary\n---\nReset ordering validation blocks this issue.",
            exact_terms=["[SV]SSD-101"],
            tags=["jira_issue", "reset-ordering", "validation"],
        ),
        DocChunk(
            chunk_id="doc-1",
            source_path="/tmp/spec.md",
            source_type="local_spec",
            doc_title="Reset Spec",
            page_or_sheet=None,
            updated_at="2026-03-29T00:00:00Z",
            source_id="local:spec",
            page_title="Reset Spec",
            heading_path=["Ordering"],
            section_path=["Ordering"],
            content="Reset ordering should be validated before recovery.",
            raw_text="Reset ordering should be validated before recovery.",
            context_prefix="Page: Reset Spec\nSection: Ordering",
            retrieval_text="Page: Reset Spec\nSection: Ordering\n---\nReset ordering should be validated before recovery.",
            exact_terms=["reset"],
            tags=["local_spec", "reset-ordering"],
        ),
    ]
    retriever = build_retriever(config, chunks)
    result = retriever.retrieve("Which Jira issue is blocked by reset ordering validation?", top_k=5)
    assert result.reranked_candidates
    assert result.reranked_candidates[0].chunk.chunk_id == "jira-1"


def test_repository_persists_extended_doc_chunk_fields(tmp_path):
    repo = Repository(str(tmp_path / "jira_summary.db"))
    chunk = DocChunk(
        chunk_id="doc-extended-1",
        source_path="/tmp/ssd.md",
        source_type="confluence_page",
        doc_title="SSD Page",
        page_or_sheet=None,
        updated_at="2026-03-30T00:00:00Z",
        source_id="confluence:1",
        page_title="SSD Page",
        heading_path=["Perf", "Timeout"],
        section_path=["Perf", "Timeout"],
        space_key="SSD",
        page_id="1",
        ancestor_titles=["Root"],
        labels=["perf"],
        authors=["tester"],
        comment_snippets=["nightly failure"],
        content="Admin timeout details",
        raw_text="Admin timeout details",
        context_prefix="Page: SSD Page",
        retrieval_text="Page: SSD Page\n---\nAdmin timeout details",
        exact_terms=["SSD-1", "1.0.7"],
        tags=["perf"],
        metadata_json={"url": "https://confluence.example.com/pages/viewpage.action?pageId=1"},
    )
    repo.save_doc_chunks([chunk])
    loaded = repo.load_doc_chunks()
    assert loaded[0].source_id == "confluence:1"
    assert loaded[0].heading_path == ["Perf", "Timeout"]
    assert loaded[0].exact_terms == ["SSD-1", "1.0.7"]


def test_answer_question_logs_hybrid_retrieval_run(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
jira:
  base_url: "https://jira.example.com"
docs:
  raw_dir: "./data/raw_docs"
  markdown_dir: "./data/markdown"
  chunks_dir: "./data/chunks"
retrieval:
  index_dir: "./data/retrieval"
storage:
  database_path: "./data/test.db"
  output_dir: "./output"
llm:
  base_url: "http://127.0.0.1:9/v1"
  api_key: "dummy"
  model: "qwen"
  timeout_seconds: 1
reporting:
  stale_days: 7
""",
        encoding="utf-8",
    )
    config = load_config(str(config_path))
    repo = Repository(config.storage.database_path)
    chunks = [
        DocChunk(
            chunk_id="jira-1",
            source_path="jira://snapshot/2026-03-30/[SV]SSD-101",
            source_type="jira_issue",
            doc_title="[SV]SSD-101 snapshot",
            page_or_sheet=None,
            updated_at="2026-03-30T00:00:00Z",
            source_id="jira:[SV]SSD-101",
            page_title="[SV]SSD-101 snapshot",
            heading_path=["Summary"],
            section_path=["Summary"],
            content="Reset ordering validation blocks this issue.",
            raw_text="Reset ordering validation blocks this issue.",
            context_prefix="Page: [SV]SSD-101 snapshot\nSection: Summary",
            retrieval_text="Page: [SV]SSD-101 snapshot\nSection: Summary\n---\nReset ordering validation blocks this issue.",
            exact_terms=["[SV]SSD-101"],
            tags=["jira_issue", "reset-ordering", "validation"],
        )
    ]
    retriever = build_retriever(config, chunks)

    result = answer_question(config, retriever, "Which Jira issue is blocked by reset ordering validation?", repo=repo)

    assert result.mode == "fallback"
    with repo.connect() as conn:
        row = conn.execute("SELECT question, query_type FROM retrieval_runs ORDER BY id DESC LIMIT 1").fetchone()
        candidate_count = conn.execute("SELECT COUNT(*) AS count FROM retrieval_candidates").fetchone()["count"]
    assert row is not None
    assert row["question"] == "Which Jira issue is blocked by reset ordering validation?"
    assert row["query_type"] == "identifier-heavy"
    assert candidate_count > 0
