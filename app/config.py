from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class JiraFilter(BaseModel):
    name: str
    url: str


class JiraFieldMapping(BaseModel):
    issue_type: str | None = None
    severity: str | None = None
    report_department: str | None = None
    root_cause: str | None = None
    frequency: str | None = None
    fail_runtime: str | None = None
    firmware_version: str | None = None
    density: str | None = None
    form_factor: str | None = None
    platform_name: str | None = None
    script_name: str | None = None
    test_step: str | None = None
    expect_result: str | None = None
    actual_result: str | None = None
    activity_comment: str | None = None
    activity_all: str | None = None


class JiraConfig(BaseModel):
    base_url: str
    access_token: str = ""
    project_filters: list[JiraFilter] = Field(default_factory=list)
    jql: str = ""
    max_results: int = 200
    timeout_seconds: int = 45
    field_mapping: JiraFieldMapping = Field(default_factory=JiraFieldMapping)


class ConfluenceConfig(BaseModel):
    base_url: str = ""
    username: str = ""
    access_token: str = ""
    crawl_mode: str = "space"
    space_keys: list[str] = Field(default_factory=list)
    root_page_urls: list[str] = Field(default_factory=list)
    page_limit: int = 500
    page_size: int = 50
    timeout_seconds: int = 45


class DocsConfig(BaseModel):
    raw_dir: str
    markdown_dir: str
    chunks_dir: str
    max_chunk_chars: int = 1800
    overlap_chars: int = 200
    marker_min_chars: int = 300
    supported_extensions: list[str] = Field(default_factory=list)


class RetrievalConfig(BaseModel):
    backend: str = "tantivy"
    index_dir: str = "./data/retrieval"
    bm25_top_k: int = 50
    dense_top_k: int = 50
    fused_top_k: int = 60
    rerank_top_k: int = 10
    enable_recency_bias: bool = True
    recency_half_life_days: int = 30
    source_type_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "jira_issue": 1.35,
            "jira_issue_analysis": 0.95,
            "jira_daily_analysis": 0.8,
            "confluence_page": 1.2,
            "local_spec": 1.25,
            "local_md": 1.0,
        }
    )


class EmbeddingConfig(BaseModel):
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    batch_size: int = 16
    device: str | None = None


class RerankerConfig(BaseModel):
    model_name: str = "BAAI/bge-reranker-base"
    max_length: int = 512
    device: str | None = None


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
    host: str = "0.0.0.0"
    port: int = 8000
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    cors_allow_credentials: bool = True


class AppConfig(BaseModel):
    jira: JiraConfig
    confluence: ConfluenceConfig = Field(default_factory=ConfluenceConfig)
    docs: DocsConfig
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    storage: StorageConfig
    llm: LLMConfig
    reporting: ReportingConfig
    server: ServerConfig = Field(default_factory=ServerConfig)


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JIRA_SUMMARY_", env_nested_delimiter="__")
    config: str = "./config.yaml"
    jira: dict[str, Any] = Field(default_factory=dict)
    confluence: dict[str, Any] = Field(default_factory=dict)
    docs: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    embedding: dict[str, Any] = Field(default_factory=dict)
    reranker: dict[str, Any] = Field(default_factory=dict)
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
            "confluence": env.confluence,
            "docs": env.docs,
            "retrieval": env.retrieval,
            "embedding": env.embedding,
            "reranker": env.reranker,
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
        config.retrieval.index_dir,
        config.storage.output_dir,
        Path(config.storage.database_path).parent,
    ]:
        Path(path).mkdir(parents=True, exist_ok=True)
    return config
