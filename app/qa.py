from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from requests import RequestException

from app.analysis import LLMClient
from app.config import AppConfig
from app.docs import BM25Index, SearchHit
from app.models import DailyAIAnalysis, IssueAIAnalysis, IssueRecord


@dataclass
class QAResult:
    question: str
    answer: str
    citations: list[dict[str, Any]]
    mode: str
    raw_response: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CombinedQAResult:
    question: str
    answer: str
    doc_citations: list[dict[str, Any]]
    jira_context: list[dict[str, Any]]
    mode: str
    raw_response: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def answer_question(config: AppConfig, index: BM25Index, question: str, top_k: int = 5) -> QAResult:
    hits = index.search(question, top_k=top_k)
    citations = [_citation(hit) for hit in hits]
    try:
        client = LLMClient(config)
        payload = client.chat_json(
            prompt=json.dumps(
                {
                    "question": question,
                    "retrieved_context": [
                        {
                            "source_path": hit.chunk.source_path,
                            "section_path": hit.chunk.section_path,
                            "content": hit.chunk.content,
                            "score": hit.score,
                        }
                        for hit in hits
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            schema_hint='{"answer":"string","citations":[{"source_path":"string","section_path":["string"],"quote":"string"}]}',
            scenario="docs_qa",
        )
        llm_citations = payload.get("citations")
        return QAResult(
            question=question,
            answer=str(payload.get("answer", "Insufficient evidence")),
            citations=llm_citations if isinstance(llm_citations, list) and llm_citations else citations,
            mode="llm",
            raw_response=json.dumps(payload, ensure_ascii=False),
        )
    except (RequestException, ValueError, KeyError):
        return QAResult(
            question=question,
            answer=_fallback_answer(question, hits),
            citations=citations,
            mode="fallback",
            raw_response="offline-fallback",
        )


def answer_jira_docs_question(
    config: AppConfig,
    index: BM25Index,
    jira_index: BM25Index | None,
    question: str,
    issues: list[IssueRecord],
    issue_analyses: list[IssueAIAnalysis],
    daily_analysis: DailyAIAnalysis | None = None,
    top_k: int = 5,
    top_issue_k: int = 5,
    top_jira_k: int = 3,
) -> CombinedQAResult:
    hits = _merge_hits(index.search(question, top_k=top_k), jira_index.search(question, top_k=top_jira_k) if jira_index else [])
    doc_citations = [_citation(hit) for hit in hits]
    jira_context = _select_relevant_issues(question, issues, issue_analyses, top_issue_k)
    try:
        client = LLMClient(config)
        payload = client.chat_json(
            prompt=json.dumps(
                {
                    "question": question,
                    "daily_analysis": daily_analysis.to_dict() if daily_analysis else None,
                    "relevant_jira_items": jira_context,
                    "retrieved_context": [
                        {
                            "source_path": hit.chunk.source_path,
                            "section_path": hit.chunk.section_path,
                            "content": hit.chunk.content,
                            "score": hit.score,
                        }
                        for hit in hits
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            schema_hint=(
                '{"answer":"string","doc_citations":[{"source_path":"string","section_path":["string"],"quote":"string"}],'
                '"jira_context":[{"issue_key":"string","summary":"string","status":"string","team":"string","reason":"string"}]}'
            ),
            scenario="jira_docs_qa",
        )
        return CombinedQAResult(
            question=question,
            answer=str(payload.get("answer", "Insufficient evidence")),
            doc_citations=payload.get("doc_citations") if isinstance(payload.get("doc_citations"), list) and payload.get("doc_citations") else doc_citations,
            jira_context=payload.get("jira_context") if isinstance(payload.get("jira_context"), list) and payload.get("jira_context") else jira_context,
            mode="llm",
            raw_response=json.dumps(payload, ensure_ascii=False),
        )
    except (RequestException, ValueError, KeyError):
        return CombinedQAResult(
            question=question,
            answer=_fallback_combined_answer(question, hits, jira_context, daily_analysis),
            doc_citations=doc_citations,
            jira_context=jira_context,
            mode="fallback",
            raw_response="offline-fallback",
        )


def _fallback_answer(question: str, hits: list[SearchHit]) -> str:
    if not hits:
        return "No relevant local evidence was found for this question."
    first = hits[0]
    section = " / ".join(first.chunk.section_path) if first.chunk.section_path else first.chunk.doc_title
    preview = " ".join(first.chunk.content.split())
    preview = preview[:500] + ("..." if len(preview) > 500 else "")
    return f"Based on {section}, the best local evidence says: {preview}"


def _fallback_combined_answer(
    question: str,
    hits: list[SearchHit],
    jira_context: list[dict[str, Any]],
    daily_analysis: DailyAIAnalysis | None,
) -> str:
    parts: list[str] = []
    if jira_context:
        top_issue = jira_context[0]
        parts.append(
            f"Most relevant Jira item is {top_issue['issue_key']} ({top_issue['status']}): {top_issue['summary']}."
        )
    if daily_analysis:
        parts.append(f"Daily status is {daily_analysis.overall_health}.")
    if hits:
        top_hit = hits[0]
        section = " / ".join(top_hit.chunk.section_path) if top_hit.chunk.section_path else top_hit.chunk.doc_title
        preview = " ".join(top_hit.chunk.content.split())
        preview = preview[:420] + ("..." if len(preview) > 420 else "")
        parts.append(f"Best matching knowledge evidence is from {section}: {preview}")
    if not parts:
        return "No relevant Jira or document evidence was found for this question."
    return " ".join(parts)


def _citation(hit: SearchHit) -> dict[str, Any]:
    return {
        "source_type": hit.chunk.source_type,
        "source_path": hit.chunk.source_path,
        "section_path": hit.chunk.section_path,
        "quote": " ".join(hit.chunk.content.split())[:240],
        "score": hit.score,
    }


def _select_relevant_issues(
    question: str, issues: list[IssueRecord], issue_analyses: list[IssueAIAnalysis], top_k: int
) -> list[dict[str, Any]]:
    query_tokens = set(_tokenize(question))
    analysis_map = {item.issue_key: item for item in issue_analyses}
    scored: list[tuple[int, dict[str, Any]]] = []
    for issue in issues:
        haystack = " ".join(
            filter(
                None,
                [
                    issue.issue_key,
                    issue.summary,
                    issue.status,
                    issue.assignee or "",
                    issue.description or "",
                    " ".join(issue.labels),
                    " ".join(issue.components),
                ],
            )
        )
        tokens = set(_tokenize(haystack))
        overlap = len(query_tokens & tokens)
        score = overlap
        if issue.issue_key.lower() in question.lower():
            score += 5
        if (issue.priority or "").lower() in {"high", "highest", "critical", "p0", "p1"}:
            score += 2
        if "block" in issue.status.lower():
            score += 2
        analysis = analysis_map.get(issue.issue_key)
        reason = f"token_overlap={overlap}"
        if analysis:
            reason = f"{reason}; ai_root_cause={analysis.suspected_root_cause}"
        if score > 0:
            scored.append(
                (
                    score,
                    {
                        "issue_key": issue.issue_key,
                        "summary": issue.summary,
                        "status": issue.status,
                        "team": issue.team,
                        "priority": issue.priority,
                        "assignee": issue.assignee,
                        "reason": reason,
                        "ai_root_cause": analysis.suspected_root_cause if analysis else "",
                        "ai_actions": analysis.action_needed if analysis else [],
                    },
                )
            )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:top_k]]


def _tokenize(text: str) -> list[str]:
    return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if token]


def _merge_hits(doc_hits: list[SearchHit], jira_hits: list[SearchHit]) -> list[SearchHit]:
    merged = sorted(doc_hits + jira_hits, key=lambda item: item.score, reverse=True)
    seen: set[str] = set()
    deduped: list[SearchHit] = []
    for hit in merged:
        if hit.chunk.chunk_id in seen:
            continue
        seen.add(hit.chunk.chunk_id)
        deduped.append(hit)
    return deduped
