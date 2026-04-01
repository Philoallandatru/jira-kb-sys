from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class JiraFilter(BaseModel):
    name: str
    url: str


class JiraConfig(BaseModel):
    base_url: str
    access_token: str = ""
    project_filters: list[JiraFilter] = Field(default_factory=list)
    jql: str = ""
    max_results: int = 200
    timeout_seconds: int = 45


class DocsConfig(BaseModel):
    raw_dir: str
    markdown_dir: str
    chunks_dir: str
    max_chunk_chars: int = 1800
    overlap_chars: int = 200
    marker_min_chars: int = 300
    supported_extensions: list[str] = Field(default_factory=list)


class StorageConfig(BaseModel):
    database_path: str
    output_dir: str


class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 120
    default_language: str = "zh-CN"
    max_output_tokens: int = 4096
    custom_prompts: dict[str, str] = Field(default_factory=dict)
    scenario_max_output_tokens: dict[str, int] = Field(default_factory=dict)


class ReportingConfig(BaseModel):
    stale_days: int = 7
    risk_keywords: list[str] = Field(default_factory=list)
    top_issue_limit: int = 20
    team_filter: str | None = None


class ServerConfig(BaseModel):
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    cors_allow_credentials: bool = True


class AppConfig(BaseModel):
    jira: JiraConfig
    docs: DocsConfig
    storage: StorageConfig
    llm: LLMConfig
    reporting: ReportingConfig
    server: ServerConfig = Field(default_factory=ServerConfig)


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JIRA_SUMMARY_", env_nested_delimiter="__")
    config: str = "./config.yaml"
    jira: dict[str, Any] = Field(default_factory=dict)
    docs: dict[str, Any] = Field(default_factory=dict)
    storage: dict[str, Any] = Field(default_factory=dict)
    llm: dict[str, Any] = Field(default_factory=dict)
    reporting: dict[str, Any] = Field(default_factory=dict)
    server: dict[str, Any] = Field(default_factory=dict)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: str | None = None) -> AppConfig:
    env = EnvSettings()
    resolved = Path(config_path or env.config)
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    merged = _deep_merge(
        data,
        {
            "jira": env.jira,
            "docs": env.docs,
            "storage": env.storage,
            "llm": env.llm,
            "reporting": env.reporting,
            "server": env.server,
        },
    )
    config = AppConfig.model_validate(merged)
    for path in [
        config.docs.raw_dir,
        config.docs.markdown_dir,
        config.docs.chunks_dir,
        config.storage.output_dir,
        Path(config.storage.database_path).parent,
    ]:
        Path(path).mkdir(parents=True, exist_ok=True)
    return config
