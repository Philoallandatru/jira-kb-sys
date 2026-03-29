from app.docs import BM25Index
from app.models import DocChunk


def test_bm25_search_returns_hit():
    chunks = [
        DocChunk(
            chunk_id="doc-1",
            source_path="/tmp/a.pdf",
            source_type="pdf",
            doc_title="Spec",
            section_path=["NVMe"],
            page_or_sheet="1",
            content="admin queue timeout handling and retry policy",
            tags=["pdf", "nvme"],
            updated_at="2026-03-30T00:00:00Z",
        )
    ]
    hits = BM25Index(chunks).search("timeout retry", top_k=3)
    assert hits
    assert hits[0].chunk.chunk_id == "doc-1"
