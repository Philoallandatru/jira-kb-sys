from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from app.config import AppConfig


class QueryType:
    IDENTIFIER_HEAVY = "identifier-heavy"
    ROOT_CAUSE = "root-cause"
    SPEC_LOOKUP = "spec-lookup"
    HISTORY_SIMILARITY = "history-similarity"
    GENERAL = "general"


@dataclass
class QueryPlan:
    query_type: str
    bm25_top_k: int
    dense_top_k: int
    fused_top_k: int
    rerank_top_k: int
    preferred_source_types: list[str]
    force_include_source_types: list[str]
    enable_recency_bias: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


IDENTIFIER_PATTERNS = [
    re.compile(r"\[[A-Z]{2,8}\][A-Z0-9_-]+-\d+|[A-Z][A-Z0-9_-]+-\d+"),
    re.compile(r"\b(?:fw[-_ ]?)?\d+(?:\.\d+){1,3}\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{2,}[0-9]{2,}\b"),
]


def build_query_plan(config: AppConfig, question: str) -> QueryPlan:
    lowered = question.lower()
    query_type = QueryType.GENERAL
    preferred = ["confluence_page", "local_spec", "jira_issue"]
    force_include: list[str] = []

    asks_for_issue = any(token in lowered for token in ("jira issue", "issue key", "which issue", "which jira", "ticket"))
    asks_root_cause = any(token in lowered for token in ("root cause", "根因", "原因", "why", "复盘", "分析"))
    asks_spec = any(token in lowered for token in ("spec", "规范", "设计", "预期", "requirement", "policy"))
    asks_history = any(token in lowered for token in ("similar", "历史", "之前", "相似", "以前", "past issue"))

    if any(pattern.search(question) for pattern in IDENTIFIER_PATTERNS) or asks_for_issue:
        query_type = QueryType.IDENTIFIER_HEAVY
        preferred = ["jira_issue", "confluence_page", "local_spec"]
        force_include = ["jira_issue"]
    elif asks_root_cause:
        query_type = QueryType.ROOT_CAUSE
        preferred = ["jira_issue", "confluence_page", "local_spec"]
        force_include = ["jira_issue"]
    elif asks_spec:
        query_type = QueryType.SPEC_LOOKUP
        preferred = ["local_spec", "confluence_page", "jira_issue"]
    elif asks_history:
        query_type = QueryType.HISTORY_SIMILARITY
        preferred = ["jira_issue", "jira_issue_analysis", "confluence_page"]
        force_include = ["jira_issue"]

    bm25_top_k = config.retrieval.bm25_top_k
    if query_type == QueryType.IDENTIFIER_HEAVY:
        bm25_top_k = max(bm25_top_k, 80)

    return QueryPlan(
        query_type=query_type,
        bm25_top_k=bm25_top_k,
        dense_top_k=config.retrieval.dense_top_k,
        fused_top_k=config.retrieval.fused_top_k,
        rerank_top_k=config.retrieval.rerank_top_k,
        preferred_source_types=preferred,
        force_include_source_types=force_include,
        enable_recency_bias=config.retrieval.enable_recency_bias,
    )
