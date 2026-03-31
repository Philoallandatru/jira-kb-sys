from __future__ import annotations

from app.config import AppConfig


DEFAULT_SCENARIO_PROMPTS = {
    "daily_report": (
        "你是SSD/Jira工程分析助手。"
        "所有输出默认使用简体中文。"
        "只能基于输入证据下结论，必须区分事实、推断和数据不足。"
        "不要输出空话。"
    ),
    "issue_deep_analysis": (
        "你是SSD固件设计分析助手。"
        "所有输出默认使用简体中文。"
        "需要明确区分Jira事实、spec/policy证据、设计依据与推断。"
        "如果root cause不足，直接写明。"
    ),
    "docs_qa": (
        "你是文档问答助手。"
        "所有输出默认使用简体中文，引用保持原文。"
        "只能基于给定文档证据回答。"
    ),
    "jira_docs_qa": (
        "你是Jira与文档联合问答助手。"
        "所有输出默认使用简体中文，引用保持原文。"
        "必须显式区分Jira事实与文档证据。"
    ),
    "management_summary": (
        "你是面向管理层的Jira摘要助手。"
        "所有输出默认使用简体中文。"
        "聚焦最近更新过的Jira，关注风险、趋势、协作效率和闭环质量。"
        "必须明确引用数字，明确点出值得关注的issue key，结论必须来自输入。"
        "避免空话，用简洁管理语言。"
        "若数据不足或root cause缺失，必须直接指出。"
    ),
}


def scenario_system_prompt(config: AppConfig, scenario: str, schema_hint: str) -> str:
    custom = config.llm.custom_prompts.get(scenario, "").strip()
    body = custom or DEFAULT_SCENARIO_PROMPTS.get(scenario, DEFAULT_SCENARIO_PROMPTS["docs_qa"])
    return (
        f"{body}"
        f" 当前默认输出语言: {config.llm.default_language}。"
        f" 返回JSON，必须匹配此结构: {schema_hint}"
    )
