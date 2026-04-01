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
        self.href_stack: list[str | None] = []
        self.list_stack: list[str] = []
        self.current_href: str | None = None
        self.current_heading_level: int | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = dict(attrs)
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
            self.lines.append("`")

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

    def handle_data(self, data: str) -> None:
        text = html.unescape(data)
        if not text.strip():
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
        client = self._build_client()
        root_page_ids = {page_id for page_id in (self._extract_page_id(url) for url in self.config.root_page_urls) if page_id}
        documents: list[MarkdownDocument] = []
        if not self.config.space_keys:
            return documents
        for space_key in self.config.space_keys:
            documents.extend(self._crawl_space_documents(client, space_key, root_page_ids))
        return documents

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
                expand="body.storage,version,ancestors,space",
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
        body_html = (((page.get("body") or {}).get("storage") or {}).get("value")) or ""
        markdown = self._render_page_markdown(title, space_key, page_id, ancestors, page)
        path_slug = _slugify("/".join([space_key, *ancestors, title]))
        markdown_path = self.markdown_dir / "confluence" / space_key / f"{path_slug}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        updated_at = ((((page.get("version") or {}).get("when")) or utc_now_iso()))
        return MarkdownDocument(
            document_id=f"confluence-{space_key.lower()}-{page_id}",
            source_path=self._page_web_url(page),
            source_type="confluence_page",
            title=title,
            markdown_path=str(markdown_path.resolve()),
            content=markdown,
            updated_at=updated_at,
        )

    def _render_page_markdown(
        self,
        title: str,
        space_key: str,
        page_id: str,
        ancestors: list[str],
        page: dict,
    ) -> str:
        parser = _HTMLToMarkdownParser()
        body_html = (((page.get("body") or {}).get("storage") or {}).get("value")) or ""
        parser.feed(body_html)
        content = parser.get_markdown()
        lines = [
            f"# {title}",
            "",
            "## Metadata",
            f"- Source Type: confluence_page",
            f"- Space: {space_key}",
            f"- Page ID: {page_id}",
            f"- URL: {self._page_web_url(page)}",
            f"- Ancestors: {' / '.join(ancestors) if ancestors else 'None'}",
            f"- Updated At: {(((page.get('version') or {}).get('when')) or 'Unknown')}",
            "",
            "## Content",
            content.strip() or "No content",
            "",
        ]
        return "\n".join(lines)

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


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower() or "confluence-page"
