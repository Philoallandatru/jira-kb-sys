from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import api


def test_api_exposes_sync_and_jira_health_routes():
    routes = {(route.path, tuple(sorted(route.methods or []))) for route in api.app.routes}

    assert ("/tasks/crawl", ("POST",)) in routes
    assert ("/tasks/sync/full", ("POST",)) in routes
    assert ("/tasks/sync/incremental", ("POST",)) in routes
    assert ("/integrations/jira/health", ("GET",)) in routes


def test_get_jira_connection_health_success(monkeypatch):
    fake_config = SimpleNamespace(jira=SimpleNamespace(base_url="https://jira.example.com"))

    class FakeCrawler:
        def __init__(self, config):
            self.config = config

        def check_connection(self):
            return {
                "ok": True,
                "base_url": self.config.base_url,
                "server_title": "Example Jira",
                "version": "9.0.0",
                "deployment_type": "Server",
                "authenticated_user": "Codex",
                "project_filter_count": 1,
                "has_jql": True,
            }

    monkeypatch.setattr(api, "_bootstrap", lambda config_path=None: (fake_config, None))
    monkeypatch.setattr(api, "JiraCrawler", FakeCrawler)

    result = api.get_jira_connection_health()

    assert result["ok"] is True
    assert result["base_url"] == "https://jira.example.com"
    assert result["authenticated_user"] == "Codex"


def test_get_jira_connection_health_failure(monkeypatch):
    fake_config = SimpleNamespace(jira=SimpleNamespace(base_url="https://jira.example.com"))

    class FakeCrawler:
        def __init__(self, config):
            self.config = config

        def check_connection(self):
            raise api.CrawlerError("Failed to connect to Jira at https://jira.example.com: boom")

    monkeypatch.setattr(api, "_bootstrap", lambda config_path=None: (fake_config, None))
    monkeypatch.setattr(api, "JiraCrawler", FakeCrawler)

    with pytest.raises(HTTPException) as exc_info:
        api.get_jira_connection_health()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["ok"] is False
    assert exc_info.value.detail["base_url"] == "https://jira.example.com"
