from pathlib import Path

from app.config import ConfluenceConfig, DocsConfig
from app.confluence import ConfluenceCrawler, ConfluenceError, storage_to_markdownish


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


def test_confluence_crawler_deduplicates_duplicate_pages(tmp_path, monkeypatch):
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

    page = {
        "id": "42",
        "title": "Policy Overview",
        "space": {"key": "SSD"},
        "version": {"when": "2026-04-01T10:00:00.000+0000"},
        "ancestors": [{"id": "1", "title": "Root"}],
        "body": {"storage": {"value": "<p>Hello</p>"}},
        "_links": {"webui": "/pages/viewpage.action?pageId=42"},
    }

    class FakeClient:
        def get_all_pages_from_space(self, space, start, limit, expand, status):
            if start > 0:
                return []
            return [page, dict(page)]

    monkeypatch.setattr(crawler, "_build_client", lambda: FakeClient())

    documents = crawler.crawl_documents()

    assert len(documents) == 1
    assert documents[0].document_id == "confluence-ssd-42"


def test_confluence_crawler_rejects_root_urls_without_page_id(tmp_path, monkeypatch):
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
            root_page_urls=["https://confluence.example.com/display/SSD/Policy+Overview"],
        ),
        docs_config,
    )

    monkeypatch.setattr(crawler, "_build_client", lambda: object())

    try:
        crawler.crawl_documents()
        assert False, "Expected ConfluenceError for root URL without pageId"
    except ConfluenceError as exc:
        assert "pageId" in str(exc)


def test_storage_to_markdownish_preserves_structure_and_filters_noise():
    storage_html = """
    <ac:structured-macro ac:name="toc"></ac:structured-macro>
    <h1>Known Regressions</h1>
    <p>FW 1.0.7 regressed reset ordering validation.</p>
    <ac:structured-macro ac:name="warning"><ac:rich-text-body><p>Do not skip recovery validation.</p></ac:rich-text-body></ac:structured-macro>
    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Error Code</td><td>0xDEAD</td></tr>
    </table>
    <pre>timeout waiting for admin queue</pre>
    """

    markdown = storage_to_markdownish(storage_html)

    assert "Known Regressions" in markdown
    assert "FW 1.0.7 regressed reset ordering validation." in markdown
    assert "[WARNING]" in markdown
    assert "Field | Value" in markdown
    assert "timeout waiting for admin queue" in markdown
    assert "toc" not in markdown.lower()
