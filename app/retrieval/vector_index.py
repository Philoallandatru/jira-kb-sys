from __future__ import annotations

import math
from collections import Counter

from app.docs import SearchHit
from app.models import DocChunk


def _normalize_tokens(text: str) -> list[str]:
    return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if token]


class VectorIndex:
    def __init__(self, chunks: list[DocChunk]) -> None:
        self.chunks = chunks
        self.chunk_vectors = [_encode_text(chunk.retrieval_text) for chunk in chunks]

    def search(self, query: str, top_k: int) -> list[SearchHit]:
        query_vec = _encode_text(query)
        scored = []
        for chunk, vector in zip(self.chunks, self.chunk_vectors):
            score = _cosine_similarity(query_vec, vector)
            if score > 0:
                scored.append(SearchHit(chunk=chunk, score=score))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


def _encode_text(text: str) -> dict[str, float]:
    tokens = _normalize_tokens(text)
    counter = Counter(tokens)
    return {token: 1.0 + math.log(freq) for token, freq in counter.items()}


def _cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    numerator = 0.0
    for token, value in left.items():
        numerator += value * right.get(token, 0.0)
    if numerator <= 0:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)
