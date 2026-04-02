from __future__ import annotations

from dataclasses import dataclass, field

from app.models import DocChunk


@dataclass
class RetrievalCandidate:
    chunk: DocChunk
    bm25_score: float = 0.0
    dense_score: float = 0.0
    fused_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0
    stages: list[str] = field(default_factory=list)

    def as_search_hit(self):
        from app.docs import SearchHit

        return SearchHit(chunk=self.chunk, score=self.final_score or self.rerank_score or self.fused_score or self.bm25_score or self.dense_score)


@dataclass
class RetrievalResult:
    question: str
    query_type: str
    plan: dict[str, object]
    bm25_candidates: list[RetrievalCandidate] = field(default_factory=list)
    dense_candidates: list[RetrievalCandidate] = field(default_factory=list)
    fused_candidates: list[RetrievalCandidate] = field(default_factory=list)
    reranked_candidates: list[RetrievalCandidate] = field(default_factory=list)

    @property
    def top_hits(self):
        return [item.as_search_hit() for item in self.reranked_candidates]
