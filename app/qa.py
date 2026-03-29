from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from requests import RequestException

from app.analysis import LLMClient
from app.config import AppConfig
from app.docs import BM25Index, SearchHit


@dataclass
class QAResult:
    question: str
    answer: str
    citations: list[dict[str, Any]]
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


def _fallback_answer(question: str, hits: list[SearchHit]) -> str:
    if not hits:
        return "No relevant local evidence was found for this question."
    first = hits[0]
    section = " / ".join(first.chunk.section_path) if first.chunk.section_path else first.chunk.doc_title
    preview = " ".join(first.chunk.content.split())
    preview = preview[:500] + ("..." if len(preview) > 500 else "")
    return f"Based on {section}, the best local evidence says: {preview}"


def _citation(hit: SearchHit) -> dict[str, Any]:
    return {
        "source_path": hit.chunk.source_path,
        "section_path": hit.chunk.section_path,
        "quote": " ".join(hit.chunk.content.split())[:240],
        "score": hit.score,
    }
