from __future__ import annotations

import json
from pathlib import Path

from app.docs import BM25Index, SearchHit, tokenize
from app.models import DocChunk


def _weighted_text(chunk: DocChunk) -> str:
    parts = []
    parts.extend([chunk.page_title] * 3)
    parts.extend(chunk.heading_path * 2)
    parts.extend(chunk.labels * 2)
    parts.extend(chunk.exact_terms * 4)
    parts.append(chunk.retrieval_text)
    parts.append(chunk.raw_text)
    if chunk.space_key:
        parts.append(chunk.space_key)
    if chunk.page_id:
        parts.append(chunk.page_id)
    return "\n".join(part for part in parts if part)


class TantivyIndex:
    def __init__(self, index_dir: str, chunks: list[DocChunk]) -> None:
        self.index_dir = Path(index_dir)
        self.chunks = chunks
        self._fallback_index = BM25Index([_fallback_chunk(chunk) for chunk in chunks])
        self._tantivy = None
        self._schema = None
        self._searcher = None
        self._query_parser = None
        self._writer = None
        self._doc_lookup = {chunk.chunk_id: chunk for chunk in chunks}
        self._load_or_build()

    def search(self, query: str, top_k: int) -> list[SearchHit]:
        if self._searcher and self._query_parser:
            try:
                parsed = self._query_parser(query)
                docs = self._searcher.search(parsed, top_k).hits
                hits: list[SearchHit] = []
                for score, addr in docs:
                    stored_doc = self._searcher.doc(addr)
                    chunk_id = stored_doc["chunk_id"][0]
                    chunk = self._doc_lookup.get(chunk_id)
                    if chunk:
                        hits.append(SearchHit(chunk=chunk, score=float(score)))
                if hits:
                    return hits
            except Exception:
                pass
        return self._fallback_index.search(query, top_k=top_k)

    def persist_manifest(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        manifest = self.index_dir / "chunks.json"
        manifest.write_text(json.dumps([chunk.to_dict() for chunk in self.chunks], ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_or_build(self) -> None:
        self.persist_manifest()
        try:
            import tantivy
        except Exception:
            return

        try:
            self.index_dir.mkdir(parents=True, exist_ok=True)
            builder = tantivy.SchemaBuilder()
            for field in ("chunk_id", "page_title", "heading_path", "labels", "exact_terms", "retrieval_text", "raw_text", "source_type"):
                builder.add_text_field(field, stored=True)
            self._schema = builder.build()
            index = tantivy.Index(self._schema, path=str(self.index_dir))
            self._writer = index.writer()
            self._writer.delete_all_documents()
            for chunk in self.chunks:
                self._writer.add_document(
                    tantivy.Document(
                        **{
                            "chunk_id": chunk.chunk_id,
                            "page_title": chunk.page_title,
                            "heading_path": " > ".join(chunk.heading_path),
                            "labels": ", ".join(chunk.labels),
                            "exact_terms": " ".join(chunk.exact_terms),
                            "retrieval_text": chunk.retrieval_text,
                            "raw_text": chunk.raw_text,
                            "source_type": chunk.source_type,
                        }
                    )
                )
            self._writer.commit()
            self._searcher = index.searcher()
            self._query_parser = index.parse_query
        except Exception:
            self._schema = None
            self._searcher = None
            self._query_parser = None
            self._writer = None


def _fallback_chunk(chunk: DocChunk) -> DocChunk:
    return DocChunk(
        chunk_id=chunk.chunk_id,
        source_path=chunk.source_path,
        source_type=chunk.source_type,
        doc_title=chunk.doc_title,
        page_or_sheet=chunk.page_or_sheet,
        updated_at=chunk.updated_at,
        source_id=chunk.source_id,
        page_title=chunk.page_title,
        section_path=list(chunk.section_path),
        heading_path=list(chunk.heading_path),
        space_key=chunk.space_key,
        page_id=chunk.page_id,
        ancestor_titles=list(chunk.ancestor_titles),
        labels=list(chunk.labels),
        authors=list(chunk.authors),
        comment_snippets=list(chunk.comment_snippets),
        content=_weighted_text(chunk),
        raw_text=chunk.raw_text,
        context_prefix=chunk.context_prefix,
        retrieval_text=chunk.retrieval_text,
        exact_terms=list(chunk.exact_terms),
        tags=list(dict.fromkeys([*chunk.tags, *tokenize(" ".join(chunk.exact_terms))])),
        metadata_json=dict(chunk.metadata_json),
    )
