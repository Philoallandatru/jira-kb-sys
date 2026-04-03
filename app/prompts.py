from __future__ import annotations

from app.config import AppConfig


DEFAULT_SCENARIO_PROMPTS = {
    "daily_report": (
        "你是 SSD/Jira 日报分析助手。"
        "所有输出默认使用简体中文。"
        "只能基于输入证据下结论，必须明确区分事实、推断和数据不足。"
        "避免空话，优先输出可执行结论。"
    ),
    "issue_deep_analysis": (
        "你是 SSD 固件 Jira 深度分析助手。"
        "所有输出默认使用简体中文。"
        "必须明确区分 Jira 事实、spec/policy 证据、评论讨论、设计依据与推断。"
        "固定输出评论洞察，包括评论摘要、关键讨论点、风险或阻塞、结论或行动项。"
        "如果 root cause 证据不足，必须直接说明。"
    ),
    "docs_qa": (
        "你是文档问答助手。"
        "所有输出默认使用简体中文，引用保持原文。"
        "只能基于给定文档证据回答。"
    ),
    "jira_docs_qa": (
        "你是 Jira 与文档联合问答助手。"
        "所有输出默认使用简体中文，引用保持原文。"
        "必须显式区分 Jira 事实和文档证据。"
    ),
    "management_summary": (
        "你是面向项目管理的 Jira 摘要助手。"
        "所有输出默认使用简体中文。"
        "聚焦最近更新过的 Jira，关注风险、趋势、协作效率和闭环质量。"
        "必须明确引用数字，明确指出值得关注的 issue key，结论必须来自输入。"
        "避免空话，使用简洁的项目管理语言。"
        "若数据不足或 root cause 缺失，必须直接指出。"
    ),
}


def scenario_system_prompt(config: AppConfig, scenario: str, schema_hint: str) -> str:
    custom = config.llm.custom_prompts.get(scenario, "").strip()
    body = custom or DEFAULT_SCENARIO_PROMPTS.get(scenario, DEFAULT_SCENARIO_PROMPTS["docs_qa"])
    return (
        f"{body}"
        f" 当前默认输出语言: {config.llm.default_language}。"
        f" 返回 JSON，必须匹配此结构: {schema_hint}"
    )
