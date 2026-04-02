from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.config import ConfluenceConfig, DocsConfig
from app.models import MarkdownDocument, utc_now_iso


class ConfluenceError(RuntimeError):
    pass


class _HTMLToMarkdownParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.list_stack: list[str] = []
        self.current_href: str | None = None
        self.current_heading_level: int | None = None
        self.in_code = False
        self.in_pre = False
        self.in_table = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.table_rows: list[list[str]] = []
        self.panel_kind: str | None = None
        self.panel_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = dict(attrs)
        if tag == "ac:structured-macro":
            macro_name = attrs_map.get("ac:name", "").lower()
            if macro_name in {"info", "note", "warning", "tip"}:
                self.panel_kind = macro_name.upper()
                self.panel_buffer = []
            if macro_name in {"toc", "children", "contributors", "contentbylabel", "pagetree"}:
                self.panel_kind = "IGNORE"
                self.panel_buffer = []
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._ensure_break()
            self.current_heading_level = int(tag[1])
            self.lines.append("#" * self.current_heading_level + " ")
        elif tag == "p":
            self._ensure_break()
        elif tag in {"ul", "ol"}:
            self.list_stack.append(tag)
            self._ensure_break()
        elif tag == "li":
            self._ensure_break()
            bullet = "- " if (self.list_stack[-1] if self.list_stack else "ul") == "ul" else "1. "
            self.lines.append(bullet)
        elif tag == "br":
            self.lines.append("\n")
        elif tag == "a":
            self.current_href = attrs_map.get("href")
        elif tag == "code":
            self.in_code = True
            self.lines.append("`")
        elif tag == "pre":
            self._ensure_break()
            self.in_pre = True
            self.lines.append("```text\n")
        elif tag == "table":
            self._ensure_break()
            self.in_table = True
            self.current_row = []
            self.table_rows = []
        elif tag == "tr" and self.in_table:
            self.current_row = []
        elif tag in {"td", "th"} and self.in_table:
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li"}:
            self.lines.append("\n")
            self.current_heading_level = None
        elif tag in {"ul", "ol"}:
            if self.list_stack:
                self.list_stack.pop()
            self.lines.append("\n")
        elif tag == "a":
            self.current_href = None
        elif tag == "code":
            self.lines.append("`")
            self.in_code = False
        elif tag == "pre":
            if not self.lines or not self.lines[-1].endswith("\n"):
                self.lines.append("\n")
            self.lines.append("```\n")
            self.in_pre = False
        elif tag in {"td", "th"} and self.in_table:
            cell = "".join(self.current_cell).strip()
            self.current_row.append(cell)
            self.current_cell = []
        elif tag == "tr" and self.in_table:
            if any(cell for cell in self.current_row):
                self.table_rows.append(list(self.current_row))
            self.current_row = []
        elif tag == "table":
            for row in self.table_rows:
                if row:
                    self.lines.append("- " + " | ".join(cell for cell in row if cell) + "\n")
            self.in_table = False
            self.table_rows = []
        elif tag == "ac:structured-macro":
            if self.panel_kind and self.panel_kind != "IGNORE":
                content = " ".join("".join(self.panel_buffer).split())
                if content:
                    self._ensure_break()
                    self.lines.append(f"> [{self.panel_kind}] {content}\n")
            self.panel_kind = None
            self.panel_buffer = []

    def handle_data(self, data: str) -> None:
        text = html.unescape(data)
        if not text.strip():
            return
        if self.panel_kind:
            self.panel_buffer.append(text)
            return
        if self.in_table:
            self.current_cell.append(text)
            return
        self.lines.append(text)
        if self.current_href and text.strip():
            self.lines.append(f" ({self.current_href})")

    def get_markdown(self) -> str:
        text = "".join(self.lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.strip() + "\n" if text.strip() else ""

    def _ensure_break(self) -> None:
        if self.lines and not self.lines[-1].endswith("\n"):
            self.lines.append("\n")


class ConfluenceCrawler:
    def __init__(self, config: ConfluenceConfig, docs_config: DocsConfig) -> None:
        self.config = config
        self.docs_config = docs_config
        self.markdown_dir = Path(docs_config.markdown_dir)

    def check_connection(self) -> dict[str, object]:
        client = self._build_client()
        spaces = []
        try:
            payload = client.get_all_spaces(start=0, limit=min(5, max(1, self.config.page_size))) or {}
            spaces = [item.get("key") for item in payload.get("results", []) if item.get("key")]
        except Exception:
            spaces = []
        return {
            "ok": True,
            "base_url": self.config.base_url,
            "authenticated_user": self.config.username or None,
            "crawl_mode": self.config.crawl_mode,
            "space_keys": self.config.space_keys,
            "sample_spaces": spaces,
        }

    def crawl_documents(self) -> list[MarkdownDocument]:
        if self.config.crawl_mode != "space":
            raise ConfluenceError(f"Unsupported Confluence crawl_mode `{self.config.crawl_mode}`. Only `space` is supported.")
        client = self._build_client()
        root_page_ids = self._resolve_root_page_ids()
        documents_by_id: dict[str, MarkdownDocument] = {}
        if not self.config.space_keys:
            return []
        for space_key in self.config.space_keys:
            for document in self._crawl_space_documents(client, space_key, root_page_ids):
                documents_by_id.setdefault(document.document_id, document)
        return list(documents_by_id.values())

    def _crawl_space_documents(self, client, space_key: str, root_page_ids: set[str]) -> list[MarkdownDocument]:
        start = 0
        fetched = 0
        documents: list[MarkdownDocument] = []
        page_size = max(1, self.config.page_size)
        while fetched < self.config.page_limit:
            batch = client.get_all_pages_from_space(
                space=space_key,
                start=start,
                limit=min(page_size, self.config.page_limit - fetched),
                expand="body.storage,version,version.by,ancestors,space,metadata.labels,comments.body.storage",
                status="current",
            ) or []
            if not batch:
                break
            for page in batch:
                if root_page_ids and not self._is_under_roots(page, root_page_ids):
                    continue
                document = self._page_to_document(page, space_key)
                documents.append(document)
            fetched += len(batch)
            start += len(batch)
            if len(batch) < page_size:
                break
        return documents

    def _page_to_document(self, page: dict, space_key: str) -> MarkdownDocument:
        page_id = str(page.get("id"))
        title = str(page.get("title") or f"Confluence {page_id}")
        ancestors = [item.get("title", "") for item in page.get("ancestors", []) if item.get("title")]
        markdown = self._render_page_markdown(title, space_key, page_id, ancestors, page)
        path_slug = _slugify("/".join([space_key, *ancestors, title]))
        markdown_path = self.markdown_dir / "confluence" / space_key / f"{path_slug}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        updated_at = ((((page.get("version") or {}).get("when")) or utc_now_iso()))
        metadata = self._extract_page_metadata(page, title, space_key, page_id, ancestors)
        return MarkdownDocument(
            document_id=f"confluence-{space_key.lower()}-{page_id}",
            source_path=self._page_web_url(page),
            source_type="confluence_page",
            title=title,
            markdown_path=str(markdown_path.resolve()),
            content=markdown,
            updated_at=updated_at,
            metadata=metadata,
        )

    def _render_page_markdown(
        self,
        title: str,
        space_key: str,
        page_id: str,
        ancestors: list[str],
        page: dict,
    ) -> str:
        body_html = (((page.get("body") or {}).get("storage") or {}).get("value")) or ""
        content = storage_to_markdownish(body_html)
        metadata = self._extract_page_metadata(page, title, space_key, page_id, ancestors)
        lines = [
            f"# {title}",
            "",
            "## Metadata",
            f"- Source Type: confluence_page",
            f"- Space: {space_key}",
            f"- Page ID: {page_id}",
            f"- URL: {self._page_web_url(page)}",
            f"- Ancestors: {' / '.join(ancestors) if ancestors else 'None'}",
            f"- Labels: {', '.join(metadata['labels']) if metadata['labels'] else 'None'}",
            f"- Authors: {', '.join(metadata['authors']) if metadata['authors'] else 'Unknown'}",
            f"- Updated At: {(((page.get('version') or {}).get('when')) or 'Unknown')}",
            "",
            "## Content",
            content.strip() or "No content",
            "",
        ]
        return "\n".join(lines)

    def _extract_page_metadata(
        self,
        page: dict,
        title: str,
        space_key: str,
        page_id: str,
        ancestors: list[str],
    ) -> dict[str, object]:
        labels = []
        metadata_labels = (((page.get("metadata") or {}).get("labels")) or {})
        for item in metadata_labels.get("results", []) if isinstance(metadata_labels, dict) else []:
            name = item.get("name")
            if name:
                labels.append(str(name))
        comment_snippets = []
        for item in (((page.get("comments") or {}).get("results")) or []):
            snippet = (((item.get("body") or {}).get("storage") or {}).get("value")) or item.get("body", "")
            if snippet:
                comment_snippets.append(clean_html_text(str(snippet))[:180])
        authors = []
        author = (((page.get("version") or {}).get("by")) or {})
        if isinstance(author, dict):
            for key in ("displayName", "email", "username", "publicName"):
                if author.get(key):
                    authors.append(str(author[key]))
                    break
        return {
            "source_id": f"confluence:{page_id}",
            "space_key": space_key,
            "page_id": page_id,
            "page_title": title,
            "ancestor_titles": ancestors,
            "labels": labels,
            "authors": authors,
            "comment_snippets": comment_snippets,
            "url": self._page_web_url(page),
        }

    def _build_client(self):
        if not self.config.base_url.strip():
            raise ConfluenceError("Confluence base_url is not configured.")
        if not self.config.username.strip() or not self.config.access_token.strip():
            raise ConfluenceError("Confluence username/access_token are required for Basic + Token auth.")
        try:
            from atlassian import Confluence
        except ImportError as exc:
            raise ConfluenceError(
                "atlassian-python-api is not installed. Install project dependencies first."
            ) from exc
        try:
            return Confluence(
                url=self.config.base_url,
                username=self.config.username,
                password=self.config.access_token,
                cloud=False,
                timeout=self.config.timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover
            raise ConfluenceError(f"Failed to connect to Confluence at {self.config.base_url}: {exc}") from exc

    def _is_under_roots(self, page: dict, root_page_ids: set[str]) -> bool:
        page_id = str(page.get("id"))
        ancestor_ids = {str(item.get("id")) for item in page.get("ancestors", []) if item.get("id") is not None}
        return page_id in root_page_ids or bool(ancestor_ids & root_page_ids)

    def _page_web_url(self, page: dict) -> str:
        base = self.config.base_url.rstrip("/")
        webui = ((page.get("_links") or {}).get("webui")) or ""
        if webui.startswith("http://") or webui.startswith("https://"):
            return webui
        if webui:
            return base + webui
        return f"{base}/pages/viewpage.action?pageId={page.get('id')}"

    def _extract_page_id(self, url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.query:
            page_id = parse_qs(parsed.query).get("pageId", [None])[0]
            if page_id:
                return str(page_id)
        match = re.search(r"/pages/(?:viewpage.action\?pageId=)?(\d+)", url)
        if match:
            return match.group(1)
        return None

    def _resolve_root_page_ids(self) -> set[str]:
        if not self.config.root_page_urls:
            return set()
        root_page_ids: set[str] = set()
        invalid_urls: list[str] = []
        for url in self.config.root_page_urls:
            page_id = self._extract_page_id(url)
            if page_id:
                root_page_ids.add(page_id)
            else:
                invalid_urls.append(url)
        if invalid_urls:
            raise ConfluenceError(
                "Unable to extract pageId from root_page_urls. Use Confluence pageId URLs for subtree filtering: "
                + ", ".join(invalid_urls)
            )
        return root_page_ids


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower() or "confluence-page"


def clean_html_text(storage_html: str) -> str:
    if not storage_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", storage_html)
    text = html.unescape(text)
    return " ".join(text.split())


def storage_to_markdownish(storage_html: str) -> str:
    parser = _HTMLToMarkdownParser()
    parser.feed(storage_html or "")
    return parser.get_markdown()
