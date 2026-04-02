from __future__ import annotations

import math
from datetime import datetime

from app.config import AppConfig
from app.retrieval.query_planner import QueryPlan, QueryType
from app.retrieval.schema import RetrievalCandidate


class CrossEncoderReranker:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._model = None
        self._load_attempted = False

    def rerank(self, query: str, candidates: list[RetrievalCandidate], plan: QueryPlan) -> list[RetrievalCandidate]:
        if not candidates:
            return []
        model = self._load_model()
        if model is not None:
            try:
                pairs = [(query, item.chunk.retrieval_text) for item in candidates]
                scores = model.predict(pairs)
                for item, score in zip(candidates, scores):
                    item.rerank_score = float(score)
                    item.final_score = float(score)
                    item.stages.append("rerank")
                return sorted(candidates, key=lambda item: item.final_score, reverse=True)[: plan.rerank_top_k]
            except Exception:
                pass

        for item in candidates:
            item.rerank_score = _fallback_score(query, item, plan, self.config)
            item.final_score = item.rerank_score
            item.stages.append("rerank")
        return sorted(candidates, key=lambda item: item.final_score, reverse=True)[: plan.rerank_top_k]

    def _load_model(self):
        if self._load_attempted:
            return self._model
        self._load_attempted = True
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.config.reranker.model_name, max_length=self.config.reranker.max_length)
        except Exception:
            self._model = None
        return self._model


def _fallback_score(query: str, candidate: RetrievalCandidate, plan: QueryPlan, config: AppConfig) -> float:
    lowered = query.lower()
    text = candidate.chunk.retrieval_text.lower()
    score = candidate.fused_score
    for token in query.lower().split():
        if token in text:
            score += 0.4
    for term in candidate.chunk.exact_terms:
        if term.lower() in lowered:
            score += 1.2
    if candidate.chunk.page_title and candidate.chunk.page_title.lower() in lowered:
        score += 0.8
    score *= config.retrieval.source_type_weights.get(candidate.chunk.source_type, 1.0)
    if candidate.chunk.source_type in plan.preferred_source_types:
        score += 0.6
    if candidate.chunk.source_type in plan.force_include_source_types:
        score += 0.8
    if plan.query_type == QueryType.ROOT_CAUSE and candidate.chunk.source_type == "jira_issue":
        score += 0.7
    if plan.enable_recency_bias:
        score *= _recency_factor(candidate.chunk.updated_at, config.retrieval.recency_half_life_days)
    return score


def _recency_factor(updated_at: str, half_life_days: int) -> float:
    try:
        normalized = updated_at.replace("Z", "+00:00") if updated_at.endswith("Z") else updated_at
        updated = datetime.fromisoformat(normalized)
    except ValueError:
        return 1.0
    now = datetime.utcnow().replace(tzinfo=updated.tzinfo)
    age_days = max((now - updated).days, 0)
    if age_days <= 0:
        return 1.05
    return 0.5 ** (age_days / max(half_life_days, 1))
