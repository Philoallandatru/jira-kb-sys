from __future__ import annotations

import json
from typing import Any

import requests
from requests import RequestException

from app.config import AppConfig
from app.docs import BM25Index, SearchHit
from app.models import DailyAIAnalysis, DailyReport, IssueAIAnalysis, IssueRecord
from app.prompts import scenario_system_prompt


class LLMClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def chat_json(self, prompt: str, schema_hint: str, scenario: str = "docs_qa", max_output_tokens: int | None = None) -> dict[str, Any]:
        response = requests.post(
            self.config.llm.base_url.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.llm.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.llm.model,
                "temperature": 0.1,
                "messages": [
                    {
                        "role": "system",
                        "content": scenario_system_prompt(self.config, scenario, schema_hint),
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_output_tokens or self.config.llm.max_output_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=self.config.llm.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return json.loads(payload["choices"][0]["message"]["content"])


def analyze_daily_report(config: AppConfig, report: DailyReport, knowledge_index: BM25Index, issues: list[IssueRecord]) -> tuple[DailyAIAnalysis, list[IssueAIAnalysis]]:
    issue_map = {issue.issue_key: issue for issue in issues}
    issue_analyses: list[IssueAIAnalysis] = []
    issue_context = []
    try:
        client = LLMClient(config)
        for item in report.priority_issues:
            issue = issue_map.get(item.issue_key)
            if not issue:
                continue
            query = " ".join(filter(None, [issue.issue_key, issue.summary, issue.description or "", " ".join(issue.labels), " ".join(issue.components)]))
            hits = knowledge_index.search(query, top_k=5)
            analysis = _analyze_issue(client, report.report_date, issue, hits)
            issue_analyses.append(analysis)
            issue_context.append(analysis.to_dict())

        daily_response = client.chat_json(
            prompt=json.dumps({"report": report.to_dict(), "issue_analyses": issue_context}, ensure_ascii=False, indent=2),
            schema_hint='{"overall_health":"string","top_risks":["string"],"suspected_root_causes":["string"],"recommended_actions":["string"],"watch_items":["string"]}',
            scenario="daily_report",
        )
        daily_analysis = DailyAIAnalysis(
            report_date=report.report_date,
            overall_health=daily_response.get("overall_health", "Insufficient evidence"),
            top_risks=_ensure_list(daily_response.get("top_risks")),
            suspected_root_causes=_ensure_list(daily_response.get("suspected_root_causes")),
            recommended_actions=_ensure_list(daily_response.get("recommended_actions")),
            watch_items=_ensure_list(daily_response.get("watch_items")),
            raw_response=json.dumps(daily_response, ensure_ascii=False),
        )
        return daily_analysis, issue_analyses
    except (RequestException, ValueError, KeyError):
        return _fallback_daily_analysis(report, knowledge_index, issues)


def _analyze_issue(client: LLMClient, report_date: str, issue: IssueRecord, hits) -> IssueAIAnalysis:
    response = client.chat_json(
        prompt=json.dumps(
            {
                "issue": issue.to_dict(),
                "knowledge_hits": [
                    {
                        "score": hit.score,
                        "source_path": hit.chunk.source_path,
                        "section_path": hit.chunk.section_path,
                        "content": hit.chunk.content,
                    }
                    for hit in hits
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        schema_hint='{"summary":"string","suspected_root_cause":"string","evidence":["string"],"action_needed":["string"],"confidence":"low|medium|high"}',
        scenario="issue_deep_analysis",
    )
    return IssueAIAnalysis(
        report_date=report_date,
        issue_key=issue.issue_key,
        summary=response.get("summary", issue.summary),
        suspected_root_cause=response.get("suspected_root_cause", "Insufficient evidence"),
        evidence=_ensure_list(response.get("evidence")),
        action_needed=_ensure_list(response.get("action_needed")),
        confidence=str(response.get("confidence", "low")),
        raw_response=json.dumps(response, ensure_ascii=False),
    )


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def _fallback_daily_analysis(report: DailyReport, knowledge_index: BM25Index, issues: list[IssueRecord]) -> tuple[DailyAIAnalysis, list[IssueAIAnalysis]]:
    issue_map = {issue.issue_key: issue for issue in issues}
    issue_analyses: list[IssueAIAnalysis] = []
    top_risks: list[str] = []
    root_causes: list[str] = []
    actions: list[str] = []

    for item in report.priority_issues:
        issue = issue_map.get(item.issue_key)
        if not issue:
            continue
        hits = knowledge_index.search(
            " ".join(filter(None, [issue.issue_key, issue.summary, issue.description or "", " ".join(issue.labels), " ".join(issue.components)])),
            top_k=3,
        )
        analysis = _fallback_issue_analysis(report.report_date, issue, hits)
        issue_analyses.append(analysis)
        top_risks.append(f"{issue.issue_key}: {issue.status} | {issue.summary}")
        root_causes.append(f"{issue.issue_key}: {analysis.suspected_root_cause}")
        actions.extend([f"{issue.issue_key}: {item}" for item in analysis.action_needed[:1]])

    overall_health = "At risk" if report.metrics.blocked_issues or report.metrics.new_issues else "Stable"
    daily = DailyAIAnalysis(
        report_date=report.report_date,
        overall_health=overall_health,
        top_risks=top_risks[:5],
        suspected_root_causes=root_causes[:5],
        recommended_actions=actions[:5] or ["Review priority issues and validate recent state transitions."],
        watch_items=[f"Stale issues: {report.metrics.stale_issues}", f"Blocked issues: {report.metrics.blocked_issues}"],
        raw_response="offline-fallback",
    )
    return daily, issue_analyses


def _fallback_issue_analysis(report_date: str, issue: IssueRecord, hits: list[SearchHit]) -> IssueAIAnalysis:
    evidence = [f"{hit.chunk.doc_title} [{'/'.join(hit.chunk.section_path)}]" for hit in hits]
    suspected_root_cause = (
        hits[0].chunk.content.split(".")[0].strip() if hits else "Insufficient evidence from local knowledge hits"
    )
    action_needed = []
    if "block" in issue.status.lower():
        action_needed.append("Stabilize the blocker path first and isolate the exact failing state transition.")
    if "timeout" in issue.summary.lower() or "timeout" in (issue.description or "").lower():
        action_needed.append("Collect timeout logs and validate queue head/tail synchronization around reset recovery.")
    if "power" in issue.summary.lower() or "recovery" in " ".join(issue.components).lower():
        action_needed.append("Replay the recovery sequence and verify metadata checkpoint consistency.")
    if not action_needed:
        action_needed.append("Review owner, latest change, and matched design notes to decide next debug step.")
    return IssueAIAnalysis(
        report_date=report_date,
        issue_key=issue.issue_key,
        summary=issue.summary,
        suspected_root_cause=suspected_root_cause,
        evidence=evidence or ["No matching local design note found"],
        action_needed=action_needed,
        confidence="medium" if hits else "low",
        raw_response="offline-fallback",
    )
