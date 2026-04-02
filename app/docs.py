from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.config import DocsConfig
from app.models import DocChunk, MarkdownDocument, utc_now_iso
from app.retrieval.preprocess import (
    build_context_prefix,
    build_retrieval_text,
    classify_local_source_type,
    enrich_chunk,
    extract_exact_terms,
    infer_document_metadata,
)


class DocsError(RuntimeError):
    pass


@dataclass
class SearchHit:
    chunk: DocChunk
    score: float


@dataclass
class Section:
    heading_path: list[str]
    blocks: list[str]


class DocumentConverter:
    def __init__(self, config: DocsConfig) -> None:
        self.config = config
        self.raw_dir = Path(config.raw_dir)
        self.markdown_dir = Path(config.markdown_dir)
        self.chunks_dir = Path(config.chunks_dir)

    def build_documents(self) -> tuple[list[MarkdownDocument], list[DocChunk]]:
        documents: list[MarkdownDocument] = []
        chunks: list[DocChunk] = []
        for path in self._iter_source_docs():
            markdown = self._convert_to_markdown(path)
            document = self._persist_markdown(path, markdown)
            documents.append(document)
        chunks = self.build_chunks_from_documents(documents)
        return documents, chunks

    def build_chunks_from_documents(self, documents: list[MarkdownDocument]) -> list[DocChunk]:
        chunks: list[DocChunk] = []
        for document in documents:
            current_chunks = list(chunk_markdown(document, self.config.max_chunk_chars, self.config.overlap_chars))
            self._persist_chunks(document, current_chunks)
            chunks.extend(current_chunks)
        return chunks

    def _iter_source_docs(self) -> Iterable[Path]:
        exts = set(self.config.supported_extensions)
        for path in self.raw_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in exts:
                yield path

    def _convert_to_markdown(self, path: Path) -> str:
        try:
            from markitdown import MarkItDown

            converter = MarkItDown()
            try:
                result = converter.convert(str(path))
                text = getattr(result, "text_content", None) or getattr(result, "markdown", None) or str(result)
                if len(text.strip()) >= self.config.marker_min_chars or path.suffix.lower() != ".pdf":
                    return text
            except Exception:
                if path.suffix.lower() != ".pdf":
                    raise
        except ImportError:
            if path.suffix.lower() != ".pdf":
                raise DocsError("MarkItDown is not installed. Install project dependencies for non-PDF conversion.")

        if path.suffix.lower() == ".pdf":
            text = self._convert_with_pdftotext(path)
            if text.strip():
                return text
            return self._convert_with_marker(path)
        raise DocsError(f"Unable to convert {path.name}; MarkItDown is required for {path.suffix.lower()} files.")

    def _convert_with_pdftotext(self, path: Path) -> str:
        command = _find_pdftotext()
        if not command:
            return ""
        output_path = self.markdown_dir / "_tmp_pdftotext.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run([command, "-layout", str(path), str(output_path)], check=True, capture_output=True, text=True)
            text = output_path.read_text(encoding="utf-8", errors="ignore")
            return normalize_pdf_text_as_markdown(text, path.stem)
        except Exception:
            return ""
        finally:
            if output_path.exists():
                output_path.unlink()

    def _convert_with_marker(self, path: Path) -> str:
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            from marker.output import text_from_rendered
        except ImportError as exc:
            raise DocsError(f"MarkItDown conversion failed for {path.name} and marker-pdf is not installed.") from exc
        converter = PdfConverter(artifact_dict=create_model_dict())
        rendered = converter(str(path))
        text, _, _ = text_from_rendered(rendered)
        return text

    def _persist_markdown(self, source_path: Path, markdown: str) -> MarkdownDocument:
        relative = source_path.relative_to(self.raw_dir)
        markdown_path = self.markdown_dir / relative.with_suffix(".md")
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        source_type = classify_local_source_type(relative.as_posix(), _normalize_source_type(source_path.suffix.lower()))
        metadata = {
            "source_id": f"local:{relative.as_posix()}",
            "page_title": source_path.stem,
            "labels": [part.lower() for part in relative.parts[:-1] if part],
            "ancestor_titles": [part for part in relative.parts[:-1] if part],
            "authors": [],
            "comment_snippets": [],
        }
        return MarkdownDocument(
            document_id=_slugify(relative.as_posix()),
            source_path=str(source_path.resolve()),
            source_type=source_type,
            title=source_path.stem,
            markdown_path=str(markdown_path.resolve()),
            content=markdown,
            updated_at=utc_now_iso(),
            metadata=metadata,
        )

    def _persist_chunks(self, document: MarkdownDocument, chunks: list[DocChunk]) -> None:
        chunk_path = self.chunks_dir / f"{document.document_id}.json"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_path.write_text(json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2), encoding="utf-8")


def chunk_markdown(document: MarkdownDocument, max_chunk_chars: int, overlap_chars: int) -> Iterable[DocChunk]:
    document_metadata = infer_document_metadata(document)
    labels = [str(item) for item in document_metadata.get("labels", []) if str(item).strip()]
    ancestor_titles = [str(item) for item in document_metadata.get("ancestor_titles", []) if str(item).strip()]
    authors = [str(item) for item in document_metadata.get("authors", []) if str(item).strip()]
    comment_snippets = [str(item) for item in document_metadata.get("comment_snippets", []) if str(item).strip()]
    page_or_sheet = _extract_page_or_sheet(document.content)
    chunk_index = 0

    for section in _split_into_sections(document.content):
        for piece in _split_section_blocks(section.blocks, max_chunk_chars=max_chunk_chars, overlap_chars=overlap_chars):
            if _is_low_signal_chunk(piece):
                continue
            digest = hashlib.sha1(f"{document.document_id}:{chunk_index}:{piece}".encode("utf-8")).hexdigest()[:12]
            heading_path = list(section.heading_path)
            context_prefix = build_context_prefix(
                page_title=str(document_metadata.get("page_title") or document.title),
                space_key=str(document_metadata.get("space_key")) if document_metadata.get("space_key") else None,
                ancestor_titles=ancestor_titles,
                heading_path=heading_path,
                labels=labels,
                updated_at=document.updated_at,
                comment_snippets=comment_snippets,
            )
            retrieval_text = build_retrieval_text(context_prefix, piece)
            metadata_json = dict(document_metadata)
            metadata_json["heading_path"] = heading_path
            metadata_json["page_or_sheet"] = page_or_sheet
            exact_terms = extract_exact_terms(retrieval_text, metadata_json)
            tags = list(
                dict.fromkeys(
                    [
                        document.source_type,
                        *[item.lower() for item in heading_path],
                        *labels,
                        *exact_terms,
                    ]
                )
            )
            chunk = DocChunk(
                chunk_id=f"{document.document_id}-{digest}",
                source_path=document.source_path,
                source_type=document.source_type,
                doc_title=document.title,
                page_or_sheet=page_or_sheet,
                updated_at=document.updated_at,
                source_id=str(document_metadata.get("source_id") or document.source_path),
                page_title=str(document_metadata.get("page_title") or document.title),
                section_path=heading_path,
                heading_path=heading_path,
                space_key=str(document_metadata.get("space_key")) if document_metadata.get("space_key") else None,
                page_id=str(document_metadata.get("page_id")) if document_metadata.get("page_id") else None,
                ancestor_titles=ancestor_titles,
                labels=labels,
                authors=authors,
                comment_snippets=comment_snippets,
                content=piece,
                raw_text=piece,
                context_prefix=context_prefix,
                retrieval_text=retrieval_text,
                exact_terms=exact_terms,
                tags=tags,
                metadata_json=metadata_json,
            )
            yield enrich_chunk(chunk)
            chunk_index += 1


class BM25Index:
    def __init__(self, chunks: list[DocChunk]) -> None:
        self.chunks = chunks
        self.corpus = [tokenize(chunk.content + " " + " ".join(chunk.tags)) for chunk in chunks]
        self.doc_freq: dict[str, int] = {}
        self.avgdl = sum(len(doc) for doc in self.corpus) / len(self.corpus) if self.corpus else 0.0
        for doc in self.corpus:
            for token in set(doc):
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        if not self.corpus or not query.strip():
            return []
        scores = [self._score_doc(tokens, tokenize(query)) for tokens in self.corpus]
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]
        return [SearchHit(chunk=self.chunks[idx], score=float(score)) for idx, score in ranked if score > 0]

    def _score_doc(self, doc_tokens: list[str], query_tokens: list[str], k1: float = 1.5, b: float = 0.75) -> float:
        if not doc_tokens:
            return 0.0
        score = 0.0
        doc_len = len(doc_tokens)
        freq: dict[str, int] = {}
        for token in doc_tokens:
            freq[token] = freq.get(token, 0) + 1
        total_docs = len(self.corpus)
        for token in query_tokens:
            if token not in freq:
                continue
            df = self.doc_freq.get(token, 0)
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            tf = freq[token]
            denom = tf + k1 * (1 - b + b * (doc_len / self.avgdl if self.avgdl else 0.0))
            score += idf * ((tf * (k1 + 1)) / denom)
        return score


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower() or "document"


def _normalize_source_type(suffix: str) -> str:
    clean = suffix.lower().lstrip(".")
    return f"local_{clean}" if clean else "local_document"


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_./:-]+", text.lower())


def _find_pdftotext() -> str | None:
    candidates = [
        shutil.which("pdftotext"),
        r"C:\Program Files\Git\mingw64\bin\pdftotext.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def normalize_pdf_text_as_markdown(text: str, title: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    normalized: list[str] = [f"# {title}", ""]
    body_started = False
    toc_headings = _extract_toc_headings(lines)

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            normalized.append("")
            continue
        if _is_noise_line(line):
            continue
        if _is_toc_entry(line):
            continue
        prev_blank = index == 0 or not lines[index - 1].strip()
        next_blank = index == len(lines) - 1 or not lines[index + 1].strip()
        heading = _normalize_heading_line(line, prev_blank=prev_blank, next_blank=next_blank, toc_headings=toc_headings)
        if heading:
            body_started = True
            if normalized and normalized[-1] != "":
                normalized.append("")
            normalized.append(heading)
            normalized.append("")
            continue
        if not body_started and _looks_like_front_matter(line):
            normalized.append(line)
            continue
        body_started = True
        normalized.append(line)

    body = "\n".join(_collapse_blank_lines(normalized)).strip()
    return body + "\n"


def _normalize_heading_line(line: str, prev_blank: bool, next_blank: bool, toc_headings: set[tuple[str, str]]) -> str | None:
    match = re.match(r"^(\d+(?:\.\d+)*)\s+(.+?)$", line)
    if not match:
        return None
    section, heading_text = match.groups()
    if not _is_valid_section_number(section):
        return None
    heading_text = re.sub(r"\s+", " ", heading_text).strip()
    if len(heading_text) < 2:
        return None
    normalized_heading = _normalize_heading_key(heading_text)
    if toc_headings and (section, normalized_heading) not in toc_headings:
        return None
    section_depth = section.count(".") + 1
    words = [word for word in re.split(r"\s+", heading_text) if word]
    if not (prev_blank or next_blank):
        if not (section_depth >= 2 and len(words) <= 6 and "." not in heading_text and ":" not in heading_text):
            return None
    if _is_toc_entry(line):
        return None
    level = min(section_depth, 6)
    if not (_looks_like_heading_text(heading_text) or level <= 2):
        return None
    return f"{'#' * level} {section} {heading_text}"


def _looks_like_heading_text(text: str) -> bool:
    if len(text) > 100 or "`" in text:
        return False
    if text.lower().startswith(("if this ", "when this ", "where this ")):
        return False
    words = [word for word in re.split(r"\s+", text) if word]
    if len(words) > 12:
        return False
    digit_chars = sum(1 for ch in text if ch.isdigit())
    if digit_chars / max(len(text), 1) > 0.2:
        return False
    if text.isupper():
        return True
    capitalized = sum(1 for word in words if word[:1].isupper())
    return capitalized >= max(1, len(words) // 2)


def _is_toc_entry(line: str) -> bool:
    if re.search(r"\.{5,}\s*[ivxIVX0-9]+$", line):
        return True
    if re.search(r"\.{5,}\s*$", line):
        return True
    if re.match(r"^[A-Za-z].+\.{5,}\s*[ivxIVX0-9]+$", line):
        return True
    if re.match(r"^\d+(?:\.\d+)*\s+.+\.{5,}\s*[ivxIVX0-9]+$", line):
        return True
    if re.match(r"^\d+(?:\.\d+)*\s+.+\.{5,}\s*$", line):
        return True
    return False


def _is_noise_line(line: str) -> bool:
    if re.match(r"^[ivxlcdmIVXLCDM]+$", line):
        return True
    if re.match(r"^NVM Express Base Specification, Revision 2\.1$", line):
        return True
    return False


def _looks_like_front_matter(line: str) -> bool:
    return bool(
        re.search(r"(NVM Express|Revision 2\.1|SPECIFICATION DISCLAIMER|LEGAL NOTICE|Copyright)", line)
    )


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    collapsed: list[str] = []
    blank = False
    for line in lines:
        if line == "":
            if blank:
                continue
            blank = True
            collapsed.append(line)
        else:
            blank = False
            collapsed.append(line)
    return collapsed


def _is_valid_section_number(section: str) -> bool:
    parts = section.split(".")
    try:
        values = [int(part) for part in parts]
    except ValueError:
        return False
    if not values or values[0] <= 0 or values[0] > 20:
        return False
    for part, value in zip(parts, values):
        if len(part) > 1 and part.startswith("0"):
            return False
        if value > 200:
            return False
    return True


def _extract_toc_headings(lines: list[str]) -> set[tuple[str, str]]:
    headings: set[tuple[str, str]] = set()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or not _is_toc_entry(line):
            continue
        cleaned = re.sub(r"\.{5,}\s*[ivxIVX0-9]*$", "", line).strip()
        match = re.match(r"^(\d+(?:\.\d+)*)\s+(.+?)$", cleaned)
        if not match:
            continue
        section, heading_text = match.groups()
        if not _is_valid_section_number(section):
            continue
        headings.add((section, _normalize_heading_key(heading_text)))
    return headings


def _normalize_heading_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_low_signal_chunk(text: str) -> bool:
    if re.search(r"\.{8,}", text):
        dotted_lines = sum(1 for line in text.splitlines() if re.search(r"\.{8,}", line))
        if dotted_lines >= 2:
            return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    short_numeric_lines = sum(1 for line in lines if re.fullmatch(r"[ivxlcdmIVXLCDM0-9]+", line))
    if short_numeric_lines >= max(2, len(lines) // 3):
        return True
    return False


def _split_into_sections(markdown_text: str) -> list[Section]:
    sections: list[Section] = []
    heading_stack: list[tuple[int, str]] = []
    current_path: list[str] = []
    current_blocks: list[str] = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code_block = False

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        paragraph = "\n".join(line.rstrip() for line in paragraph_lines).strip()
        paragraph_lines = []
        if paragraph:
            current_blocks.append(paragraph)

    def flush_code_block() -> None:
        nonlocal code_lines
        if code_lines:
            current_blocks.append("\n".join(code_lines).strip())
            code_lines = []

    def flush_section() -> None:
        flush_paragraph()
        flush_code_block()
        if current_blocks:
            sections.append(Section(heading_path=list(current_path), blocks=list(current_blocks)))
            current_blocks.clear()

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            flush_section()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            current_path = [item[1] for item in heading_stack]
            continue
        if not line.strip():
            flush_paragraph()
            continue
        if line.startswith("```"):
            flush_paragraph()
            if in_code_block:
                code_lines.append(line)
                flush_code_block()
                in_code_block = False
            else:
                flush_code_block()
                code_lines = [line]
                in_code_block = True
            continue
        if in_code_block:
            code_lines.append(line)
            continue
        if line.startswith("> ") or line.startswith("- ") or line.startswith("1. ") or "|" in line:
            flush_paragraph()
            current_blocks.append(line)
            continue
        paragraph_lines.append(line)

    flush_section()
    if not sections:
        fallback = clean_text(markdown_text)
        if fallback:
            sections.append(Section(heading_path=[], blocks=[fallback]))
    return sections


def _split_section_blocks(blocks: list[str], *, max_chunk_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    current_blocks: list[str] = []
    current_len = 0

    def flush_current() -> None:
        nonlocal current_blocks, current_len
        text = "\n\n".join(current_blocks).strip()
        current_blocks = []
        current_len = 0
        if text:
            chunks.append(text)

    for block in blocks:
        normalized = block.strip()
        if not normalized:
            continue
        block_len = len(normalized) + 2
        if current_blocks and current_len + block_len > max_chunk_chars:
            flush_current()
        if len(normalized) > max_chunk_chars:
            for piece in _split_oversized_block(normalized, max_chunk_chars=max_chunk_chars, overlap_chars=overlap_chars):
                chunks.append(piece)
            continue
        current_blocks.append(normalized)
        current_len += block_len

    flush_current()
    return chunks


def _split_oversized_block(text: str, *, max_chunk_chars: int, overlap_chars: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chunk_chars)
        if end < len(text):
            split_at = text.rfind("\n", start, end)
            if split_at <= start:
                split_at = text.rfind(" ", start, end)
            if split_at > start:
                end = split_at
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - max(overlap_chars, 0))
    return pieces


def _extract_page_or_sheet(text: str) -> str | None:
    for line in text.splitlines():
        lowered = line.lower()
        if lowered.startswith(("page ", "sheet:")):
            return line.split(":", 1)[-1].strip() if ":" in line else line.strip()
    return None


def clean_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()
