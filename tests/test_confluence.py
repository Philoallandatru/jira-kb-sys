from pathlib import Path

from app.config import ConfluenceConfig, DocsConfig
from app.confluence import ConfluenceCrawler


def test_confluence_crawler_builds_markdown_documents_from_space_pages(tmp_path, monkeypatch):
    docs_config = DocsConfig(
        raw_dir=str(tmp_path / "raw"),
        markdown_dir=str(tmp_path / "markdown"),
        chunks_dir=str(tmp_path / "chunks"),
        supported_extensions=[".md"],
    )
    crawler = ConfluenceCrawler(
        ConfluenceConfig(
            base_url="https://confluence.example.com",
            username="codex@example.com",
            access_token="secret",
            space_keys=["SSD"],
            page_limit=10,
            page_size=10,
        ),
        docs_config,
    )

    class FakeClient:
        def get_all_pages_from_space(self, space, start, limit, expand, status):
            assert space == "SSD"
            if start > 0:
                return []
            return [
                {
                    "id": "42",
                    "title": "Policy Overview",
                    "space": {"key": "SSD"},
                    "version": {"when": "2026-04-01T10:00:00.000+0000"},
                    "ancestors": [{"id": "1", "title": "Root"}],
                    "body": {"storage": {"value": "<h1>Intro</h1><p>Hello <strong>world</strong></p>"}},
                    "_links": {"webui": "/pages/viewpage.action?pageId=42"},
                }
            ]

    monkeypatch.setattr(crawler, "_build_client", lambda: FakeClient())

    documents = crawler.crawl_documents()

    assert len(documents) == 1
    assert documents[0].source_type == "confluence_page"
    assert "Policy Overview" in documents[0].content
    markdown_path = Path(documents[0].markdown_path)
    assert markdown_path.exists()
    assert markdown_path.read_text(encoding="utf-8")
