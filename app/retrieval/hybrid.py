from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import AppConfig
from app.models import DocChunk
from app.retrieval.query_planner import QueryPlan, build_query_plan
from app.retrieval.rerank import CrossEncoderReranker
from app.retrieval.schema import RetrievalCandidate, RetrievalResult
from app.retrieval.tantivy_index import TantivyIndex
from app.retrieval.vector_index import VectorIndex

if TYPE_CHECKING:
    from app.docs import SearchHit
    from app.repository import Repository


class HybridRetriever:
    def __init__(self, config: AppConfig, chunks: list[DocChunk]) -> None:
        self.config = config
        self.chunks = chunks
        self.tantivy = TantivyIndex(config.retrieval.index_dir, chunks)
        self.vector = VectorIndex(chunks)
        self.reranker = CrossEncoderReranker(config)

    def retrieve(self, question: str, top_k: int | None = None, repo: Repository | None = None) -> RetrievalResult:
        plan = build_query_plan(self.config, question)
        bm25_hits = self._filter_hits(self.tantivy.search(question, top_k=plan.bm25_top_k), plan)
        dense_hits = self._filter_hits(self.vector.search(question, top_k=plan.dense_top_k), plan)
        fused = _rrf_fuse(bm25_hits, dense_hits, plan.fused_top_k)
        reranked = self.reranker.rerank(question, fused, plan)
        if top_k is not None:
            reranked = reranked[:top_k]

        result = RetrievalResult(
            question=question,
            query_type=plan.query_type,
            plan=plan.to_dict(),
            bm25_candidates=_to_candidates(bm25_hits, stage="bm25"),
            dense_candidates=_to_candidates(dense_hits, stage="dense"),
            fused_candidates=fused,
            reranked_candidates=reranked,
        )
        if repo is not None:
            repo.save_retrieval_run(result)
        return result

    def _filter_hits(self, hits: list[SearchHit], plan: QueryPlan) -> list[SearchHit]:
        if not plan.preferred_source_types:
            return hits
        preferred = []
        other = []
        for hit in hits:
            if hit.chunk.source_type in plan.preferred_source_types:
                preferred.append(hit)
            else:
                other.append(hit)
        combined = preferred + other
        force = [hit for hit in combined if hit.chunk.source_type in plan.force_include_source_types]
        if force:
            return _dedupe_hits(force + combined)
        return _dedupe_hits(combined)


def build_retriever(config: AppConfig, chunks: list[DocChunk]) -> HybridRetriever:
    return HybridRetriever(config, chunks)


def _rrf_fuse(bm25_hits: list[SearchHit], dense_hits: list[SearchHit], top_k: int) -> list[RetrievalCandidate]:
    pool: dict[str, RetrievalCandidate] = {}
    for rank, hit in enumerate(bm25_hits, start=1):
        candidate = pool.setdefault(hit.chunk.chunk_id, RetrievalCandidate(chunk=hit.chunk))
        candidate.bm25_score = hit.score
        candidate.fused_score += 1.0 / (60 + rank)
        candidate.stages.append("bm25")
    for rank, hit in enumerate(dense_hits, start=1):
        candidate = pool.setdefault(hit.chunk.chunk_id, RetrievalCandidate(chunk=hit.chunk))
        candidate.dense_score = hit.score
        candidate.fused_score += 1.0 / (60 + rank)
        candidate.stages.append("dense")
    fused = sorted(pool.values(), key=lambda item: item.fused_score, reverse=True)
    for item in fused:
        item.final_score = item.fused_score
    return fused[:top_k]


def _to_candidates(hits: list[SearchHit], stage: str) -> list[RetrievalCandidate]:
    candidates: list[RetrievalCandidate] = []
    for hit in hits:
        candidate = RetrievalCandidate(chunk=hit.chunk, stages=[stage], final_score=hit.score)
        if stage == "bm25":
            candidate.bm25_score = hit.score
        elif stage == "dense":
            candidate.dense_score = hit.score
        candidates.append(candidate)
    return candidates


def _dedupe_hits(hits: list[SearchHit]) -> list[SearchHit]:
    seen = set()
    deduped = []
    for hit in hits:
        if hit.chunk.chunk_id in seen:
            continue
        seen.add(hit.chunk.chunk_id)
        deduped.append(hit)
    return deduped
