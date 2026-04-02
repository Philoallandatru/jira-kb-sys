from __future__ import annotations

import re
from collections.abc import Iterable

from app.models import DocChunk, MarkdownDocument


ISSUE_KEY_RE = re.compile(r"\[[A-Z]{2,8}\][A-Z0-9_-]+-\d+|[A-Z][A-Z0-9_-]+-\d+")
VERSION_RE = re.compile(r"\b(?:fw[-_ ]?)?\d+(?:\.\d+){1,3}\b", re.IGNORECASE)
ERROR_CODE_RE = re.compile(r"\b[A-Z]{2,}[0-9]{2,}\b")
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")


def build_context_prefix(
    *,
    page_title: str,
    space_key: str | None,
    ancestor_titles: Iterable[str],
    heading_path: Iterable[str],
    labels: Iterable[str],
    updated_at: str,
    comment_snippets: Iterable[str],
) -> str:
    comments = ", ".join(_trim_comment(item) for item in comment_snippets if item.strip())
    return "\n".join(
        [
            f"Page: {page_title}",
            f"Space: {space_key or 'N/A'}",
            f"Ancestors: {' / '.join(item for item in ancestor_titles if item) or 'N/A'}",
            f"Section: {' > '.join(item for item in heading_path if item) or 'N/A'}",
            f"Labels: {', '.join(item for item in labels if item) or 'N/A'}",
            f"Updated: {updated_at}",
            f"Comments: {comments or 'N/A'}",
        ]
    )


def build_retrieval_text(context_prefix: str, raw_text: str) -> str:
    body = raw_text.strip()
    if not context_prefix.strip():
        return body
    if not body:
        return context_prefix.strip()
    return f"{context_prefix.strip()}\n---\n{body}"


def extract_exact_terms(text: str, metadata: dict[str, object] | None = None) -> list[str]:
    terms: list[str] = []
    metadata = metadata or {}
    for value in metadata.values():
        if isinstance(value, str):
            terms.extend(_extract_tokens(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    terms.extend(_extract_tokens(item))
    terms.extend(_extract_tokens(text))
    return list(dict.fromkeys(term for term in terms if term))


def enrich_chunk(chunk: DocChunk) -> DocChunk:
    metadata = dict(chunk.metadata_json)
    context_prefix = chunk.context_prefix or build_context_prefix(
        page_title=chunk.page_title or chunk.doc_title,
        space_key=chunk.space_key,
        ancestor_titles=chunk.ancestor_titles,
        heading_path=chunk.heading_path or chunk.section_path,
        labels=chunk.labels,
        updated_at=chunk.updated_at,
        comment_snippets=chunk.comment_snippets,
    )
    raw_text = chunk.raw_text or chunk.content
    retrieval_text = chunk.retrieval_text or build_retrieval_text(context_prefix, raw_text)
    exact_terms = chunk.exact_terms or extract_exact_terms(retrieval_text, metadata)
    chunk.context_prefix = context_prefix
    chunk.raw_text = raw_text
    chunk.retrieval_text = retrieval_text
    chunk.exact_terms = exact_terms
    chunk.content = raw_text
    chunk.metadata_json = metadata
    return chunk


def infer_document_metadata(document: MarkdownDocument) -> dict[str, object]:
    metadata = dict(document.metadata)
    if "source_id" not in metadata:
        metadata["source_id"] = document.source_path
    if "page_title" not in metadata:
        metadata["page_title"] = document.title
    return metadata


def classify_local_source_type(source_path: str, source_type: str) -> str:
    normalized = source_path.replace("\\", "/").lower()
    if any(token in normalized for token in ("/spec/", "/specs/", "/design/", "/policy/", "/requirements/")):
        return "local_spec"
    return source_type


def _extract_tokens(text: str) -> list[str]:
    values = []
    values.extend(match.group(0) for match in ISSUE_KEY_RE.finditer(text))
    values.extend(match.group(0) for match in VERSION_RE.finditer(text))
    values.extend(match.group(0) for match in ERROR_CODE_RE.finditer(text))
    values.extend(token for token in PATH_TOKEN_RE.findall(text) if any(ch.isdigit() for ch in token) and len(token) > 3)
    return [item.strip() for item in values]


def _trim_comment(text: str) -> str:
    return " ".join(text.split())[:80]
