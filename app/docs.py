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


class DocsError(RuntimeError):
    pass


@dataclass
class SearchHit:
    chunk: DocChunk
    score: float


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
            current_chunks = list(chunk_markdown(document, self.config.max_chunk_chars, self.config.overlap_chars))
            self._persist_chunks(document, current_chunks)
            documents.append(document)
            chunks.extend(current_chunks)
        return documents, chunks

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
        return MarkdownDocument(
            document_id=_slugify(relative.as_posix()),
            source_path=str(source_path.resolve()),
            source_type=source_path.suffix.lower().lstrip("."),
            title=source_path.stem,
            markdown_path=str(markdown_path.resolve()),
            content=markdown,
            updated_at=utc_now_iso(),
        )

    def _persist_chunks(self, document: MarkdownDocument, chunks: list[DocChunk]) -> None:
        chunk_path = self.chunks_dir / f"{document.document_id}.json"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_path.write_text(json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2), encoding="utf-8")


def chunk_markdown(document: MarkdownDocument, max_chunk_chars: int, overlap_chars: int) -> Iterable[DocChunk]:
    lines = document.content.splitlines()
    section_path: list[str] = []
    page_or_sheet: str | None = None
    buffer: list[str] = []
    chunk_index = 0

    def flush() -> list[DocChunk]:
        nonlocal buffer, chunk_index
        text = "\n".join(buffer).strip()
        buffer = []
        if not text:
            return []
        pieces = [text]
        if len(text) > max_chunk_chars:
            pieces = []
            start = 0
            while start < len(text):
                end = min(len(text), start + max_chunk_chars)
                pieces.append(text[start:end])
                if end == len(text):
                    break
                start = max(0, end - overlap_chars)
        chunks: list[DocChunk] = []
        for piece in pieces:
            if _is_low_signal_chunk(piece):
                continue
            digest = hashlib.sha1(f"{document.document_id}:{chunk_index}:{piece}".encode("utf-8")).hexdigest()[:12]
            chunks.append(
                DocChunk(
                    chunk_id=f"{document.document_id}-{digest}",
                    source_path=document.source_path,
                    source_type=document.source_type,
                    doc_title=document.title,
                    section_path=list(section_path),
                    page_or_sheet=page_or_sheet,
                    content=piece,
                    tags=[document.source_type, *[item.lower() for item in section_path]],
                    updated_at=document.updated_at,
                )
            )
            chunk_index += 1
        return chunks

    for line in lines:
        if re.match(r"^#{1,6}\s+", line):
            for chunk in flush():
                yield chunk
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip()
            section_path[:] = section_path[: level - 1]
            section_path.append(title)
        if line.lower().startswith(("page ", "sheet:")):
            page_or_sheet = line.split(":", 1)[-1].strip() if ":" in line else line.strip()
        buffer.append(line)
    for chunk in flush():
        yield chunk


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
