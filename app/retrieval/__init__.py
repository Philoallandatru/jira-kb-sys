from __future__ import annotations

from app.retrieval.query_planner import QueryPlan, QueryType
from app.retrieval.schema import RetrievalCandidate, RetrievalResult

__all__ = [
    "HybridRetriever",
    "QueryPlan",
    "QueryType",
    "RetrievalCandidate",
    "RetrievalResult",
    "build_retriever",
]


def __getattr__(name: str):
    if name in {"HybridRetriever", "build_retriever"}:
        from app.retrieval.hybrid import HybridRetriever, build_retriever

        return {"HybridRetriever": HybridRetriever, "build_retriever": build_retriever}[name]
    raise AttributeError(name)
