from __future__ import annotations

import json
from collections import Counter

from requests import RequestException

from app.analysis import LLMClient
from app.config import AppConfig
from app.docs import SearchHit
from app.jira_knowledge import filter_product_doc_chunks
from app.models import DeepAnalysisCitation, IssueAIAnalysis, IssueDeepAnalysisResult, IssueRecord, utc_now_iso
from app.repository import Repository
from app.retrieval import build_retriever


def build_issue_deep_analysis(
    config: AppConfig,
    repo: Repository,
    issue_key: str,
    snapshot_date: str | None = None,
) -> IssueDeepAnalysisResult:
    resolved_snapshot = snapshot_date or repo.latest_snapshot_date()
    if not resolved_snapshot:
        raise RuntimeError("No snapshot data found")
    issue = repo.load_issue(issue_key, resolved_snapshot)
    if not issue:
        raise RuntimeError(f"Issue `{issue_key}` not found in snapshot {resolved_snapshot}")

    chunks = filter_product_doc_chunks(repo.load_doc_chunks())
    index = build_retriever(config, chunks)
    issue_fact_sheet = _build_issue_fact_sheet(issue)
    related_hits = index.retrieve(_build_issue_query(issue), top_k=8).top_hits
    issue_analyses = {item.issue_key: item for item in repo.load_issue_analyses(resolved_snapshot)}
    related_issues = _related_issues(issue, repo.load_snapshot(resolved_snapshot), issue_analyses)

    try:
        client = LLMClient(config)
        payload = client.chat_json(
            prompt=json.dumps(
                {
                    "issue": issue.to_dict(),
                    "issue_fact_sheet": issue_fact_sheet,
                    "snapshot_date": resolved_snapshot,
                    "matched_documents": [_serialize_hit(hit) for hit in related_hits],
                    "related_issues": related_issues,
                    "existing_issue_analysis": issue_analyses.get(issue.issue_key).to_dict()
                    if issue.issue_key in issue_analyses
                    else None,
                },
                ensure_ascii=False,
                indent=2,
            ),
            schema_hint=(
                '{"issue_summary":"string","spec_relations":["string"],"policy_relations":["string"],'
                '"related_jira_designs":["string"],"comment_summary":"string","comment_key_points":["string"],'
                '"comment_risks_blockers":["string"],"comment_actions_decisions":["string"],'
                '"suspected_problems":["string"],"next_actions":["string"],'
                '"open_questions":["string"],"confidence":"low|medium|high",'
                '"citations":[{"source_type":"string","source_path":"string","section_path":["string"],"summary":"string"}]}'
            ),
            scenario="issue_deep_analysis",
        )
        return IssueDeepAnalysisResult(
            issue_key=issue.issue_key,
            generated_at=utc_now_iso(),
            issue_summary=str(payload.get("issue_summary", issue.summary)),
            spec_relations=_ensure_list(payload.get("spec_relations")),
            policy_relations=_ensure_list(payload.get("policy_relations")),
            related_jira_designs=_ensure_list(payload.get("related_jira_designs")),
            comment_summary=str(payload.get("comment_summary", "")),
            comment_key_points=_ensure_list(payload.get("comment_key_points")),
            comment_risks_blockers=_ensure_list(payload.get("comment_risks_blockers")),
            comment_actions_decisions=_ensure_list(payload.get("comment_actions_decisions")),
            suspected_problems=_ensure_list(payload.get("suspected_problems")),
            next_actions=_ensure_list(payload.get("next_actions")),
            open_questions=_ensure_list(payload.get("open_questions")),
            confidence=str(payload.get("confidence", "medium")),
            citations=_ensure_citations(payload.get("citations"), related_hits),
            raw_response=json.dumps(payload, ensure_ascii=False),
        )
    except (RequestException, ValueError, KeyError):
        return _fallback_issue_deep_analysis(issue, related_hits, related_issues, issue_analyses.get(issue.issue_key))


def _fallback_issue_deep_analysis(
    issue: IssueRecord,
    hits: list[SearchHit],
    related_issues: list[dict[str, str | list[str]]],
    cached_analysis: IssueAIAnalysis | None,
) -> IssueDeepAnalysisResult:
    spec_relations: list[str] = []
    policy_relations: list[str] = []
    citations: list[DeepAnalysisCitation] = []
    fact_sheet = _build_issue_fact_sheet(issue)
    comment_insights = _summarize_comments(issue.comments)

    for hit in hits:
        category = _categorize_hit(hit)
        summary = f"{hit.chunk.doc_title} / {' / '.join(hit.chunk.section_path)}"
        citations.append(
            DeepAnalysisCitation(
                source_type=category,
                source_path=hit.chunk.source_path,
                section_path=hit.chunk.section_path,
                summary=summary,
            )
        )
        note = f"{summary}: {' '.join(hit.chunk.content.split())[:180]}"
        if category == "policy":
            policy_relations.append(note)
        elif category == "spec":
            spec_relations.append(note)

    suspected: list[str] = []
    if cached_analysis:
        suspected.append(f"Existing issue analysis suggests the root cause may be: {cached_analysis.suspected_root_cause}")
    if "block" in issue.status.lower():
        suspected.append("The issue is still blocked, so the blocking dependency should be cleared before further execution.")
    if issue.severity and issue.severity.lower() in {"major", "highest", "high"} and not issue.root_cause:
        suspected.append("The issue is high severity, but Jira still lacks a clearly documented root cause.")
    if not spec_relations:
        spec_relations.append("No strongly relevant spec evidence was found in the local knowledge base.")
    if not policy_relations:
        policy_relations.append("No strongly relevant policy or design-guidance evidence was found in the local knowledge base.")

    next_actions = list(cached_analysis.action_needed if cached_analysis else [])
    if issue.assignee is None:
        next_actions.append("Assign a single owner before continuing the investigation or fix.")
    if not next_actions:
        next_actions.append("Collect logs, reproduce the issue, and validate actual behavior against the matched spec and policy evidence.")

    open_questions: list[str] = []
    if issue.priority and issue.priority.lower() in {"highest", "high", "critical", "p0", "p1"}:
        open_questions.append("Are the release gate and regression sign-off criteria already defined for this high-priority issue?")
    if not issue.description:
        open_questions.append("Should the Jira issue be updated with reproduction steps, impact scope, and expected behavior?")
    if not issue.fix_versions:
        open_questions.append("Should a target fix version be assigned before execution continues?")
    if fact_sheet["platform"] or fact_sheet["script_name"]:
        open_questions.append("Has the reported platform and script combination been reproduced independently?")

    return IssueDeepAnalysisResult(
        issue_key=issue.issue_key,
        generated_at=utc_now_iso(),
        issue_summary=issue.summary,
        spec_relations=spec_relations,
        policy_relations=policy_relations,
        related_jira_designs=[item["issue_key"] + ": " + str(item["summary"]) for item in related_issues[:5]],
        comment_summary=comment_insights["summary"],
        comment_key_points=comment_insights["key_points"],
        comment_risks_blockers=comment_insights["risks_blockers"],
        comment_actions_decisions=comment_insights["actions_decisions"],
        suspected_problems=suspected or ["Current evidence is still insufficient to support a stable conclusion."],
        next_actions=next_actions,
        open_questions=open_questions or ["Do we now have enough root-cause evidence to support a concrete decision?"],
        confidence="medium" if hits else "low",
        citations=citations[:6],
        raw_response="offline-fallback",
    )


def _related_issues(
    issue: IssueRecord,
    issues: list[IssueRecord],
    issue_analyses: dict[str, IssueAIAnalysis],
) -> list[dict[str, str | list[str]]]:
    current_tokens = set(_tokenize(_build_issue_query(issue)))
    current_platform = (issue.description_fields.get("Platform Name") or "").lower()
    current_script = (issue.description_fields.get("Script Name") or "").lower()
    scored = []
    for candidate in issues:
        if candidate.issue_key == issue.issue_key:
            continue
        candidate_tokens = set(_tokenize(_build_issue_query(candidate)))
        overlap = len(current_tokens & candidate_tokens)
        score = overlap
        if set(issue.components) & set(candidate.components):
            score += 4
        if issue.root_cause and candidate.root_cause and issue.root_cause == candidate.root_cause:
            score += 5
        if current_platform and current_platform == (candidate.description_fields.get("Platform Name") or "").lower():
            score += 4
        if current_script and current_script == (candidate.description_fields.get("Script Name") or "").lower():
            score += 3
        if set(issue.affects_versions) & set(candidate.affects_versions):
            score += 2
        if set(issue.blocks_links) & set(candidate.blocks_links):
            score += 3
        if score == 0:
            continue
        analysis = issue_analyses.get(candidate.issue_key)
        scored.append(
            (
                score,
                {
                    "issue_key": candidate.issue_key,
                    "summary": candidate.summary,
                    "status": candidate.status,
                    "reason": (
                        f"score={score}; token_overlap={overlap}; "
                        f"same_component={bool(set(issue.components) & set(candidate.components))}; "
                        f"same_root_cause={bool(issue.root_cause and issue.root_cause == candidate.root_cause)}"
                    ),
                    "actions": analysis.action_needed if analysis else [],
                },
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:8]]


def _serialize_hit(hit: SearchHit) -> dict[str, object]:
    return {
        "source_type": _categorize_hit(hit),
        "source_path": hit.chunk.source_path,
        "doc_title": hit.chunk.doc_title,
        "section_path": hit.chunk.heading_path,
        "score": hit.score,
        "content": hit.chunk.raw_text,
    }


def _categorize_hit(hit: SearchHit) -> str:
    title = f"{hit.chunk.doc_title} {' '.join(hit.chunk.section_path)} {hit.chunk.source_path}".lower()
    if "policy" in title or "design" in title:
        return "policy"
    if "spec" in title or "requirement" in title or "nvme" in title:
        return "spec"
    return "reference"


def _ensure_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value)]


def _ensure_citations(value: object, hits: list[SearchHit]) -> list[DeepAnalysisCitation]:
    if isinstance(value, list):
        parsed = []
        for item in value:
            if not isinstance(item, dict):
                continue
            parsed.append(
                DeepAnalysisCitation(
                    source_type=str(item.get("source_type", "reference")),
                    source_path=str(item.get("source_path", "")),
                    section_path=[str(part) for part in item.get("section_path", [])],
                    summary=str(item.get("summary", "")),
                )
            )
        if parsed:
            return parsed
    deduped = []
    seen = Counter()
    for hit in hits:
        summary = f"{hit.chunk.page_title or hit.chunk.doc_title} / {' / '.join(hit.chunk.heading_path)}"
        key = (hit.chunk.source_path, tuple(hit.chunk.section_path))
        seen[key] += 1
        if seen[key] > 1:
            continue
        deduped.append(
            DeepAnalysisCitation(
                source_type=_categorize_hit(hit),
                source_path=hit.chunk.source_path,
                section_path=hit.chunk.heading_path,
                summary=summary,
            )
        )
    return deduped[:6]


def _tokenize(text: str) -> list[str]:
    return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if token]


def _build_issue_query(issue: IssueRecord) -> str:
    values = [
        issue.issue_key,
        issue.summary,
        issue.description or "",
        issue.issue_type or "",
        issue.severity or "",
        issue.root_cause or "",
        " ".join(issue.labels),
        " ".join(issue.components),
        " ".join(issue.fix_versions),
        " ".join(issue.affects_versions),
        " ".join(issue.issue_links),
        " ".join(issue.blocks_links),
        issue.description_fields.get("Platform Name", ""),
        issue.description_fields.get("Script Name", ""),
        issue.description_fields.get("Expect Result", ""),
        issue.description_fields.get("Actual Result", ""),
    ]
    return " ".join(part for part in values if part)


def _build_issue_fact_sheet(issue: IssueRecord) -> dict[str, object]:
    comment_insights = _summarize_comments(issue.comments)
    return {
        "issue_key": issue.issue_key,
        "summary": issue.summary,
        "type": issue.issue_type,
        "status": issue.status,
        "priority": issue.priority,
        "severity": issue.severity,
        "component": issue.components,
        "root_cause": issue.root_cause,
        "fix_versions": issue.fix_versions,
        "affects_versions": issue.affects_versions,
        "report_department": issue.report_department,
        "platform": issue.description_fields.get("Platform Name"),
        "script_name": issue.description_fields.get("Script Name"),
        "firmware_version": issue.description_fields.get("Firmware Version"),
        "expect_result": issue.description_fields.get("Expect Result"),
        "actual_result": issue.description_fields.get("Actual Result"),
        "test_step": issue.description_fields.get("Test step"),
        "blocks_links": issue.blocks_links,
        "mentioned_in_links": issue.mentioned_in_links,
        "issue_links": issue.issue_links,
        "comments_count": len(issue.comments),
        "comment_summary": comment_insights["summary"],
        "comment_key_points": comment_insights["key_points"],
        "comment_risks_blockers": comment_insights["risks_blockers"],
        "comment_actions_decisions": comment_insights["actions_decisions"],
        "comment_samples": comment_insights["samples"],
    }


def _summarize_comments(comments: list[str], max_comments: int = 8, max_chars_per_comment: int = 280) -> dict[str, object]:
    trimmed = []
    for comment in comments[:max_comments]:
        normalized = " ".join(comment.split())
        if not normalized:
            continue
        trimmed.append(normalized[:max_chars_per_comment])

    if not trimmed:
        return {
            "summary": "No usable comment information is available.",
            "key_points": [],
            "risks_blockers": [],
            "actions_decisions": [],
            "samples": [],
        }

    key_points = trimmed[:3]
    risks_blockers = []
    actions_decisions = []
    risk_keywords = ("risk", "block", "blocked", "failure", "timeout", "panic", "stuck", "异常", "风险", "阻塞")
    action_keywords = ("todo", "action", "next", "follow", "fix", "owner", "结论", "行动", "处理", "修复", "跟进")
    for item in trimmed:
        lowered = item.lower()
        if any(keyword in lowered for keyword in risk_keywords) and item not in risks_blockers:
            risks_blockers.append(item)
        if any(keyword in lowered for keyword in action_keywords) and item not in actions_decisions:
            actions_decisions.append(item)

    if not risks_blockers:
        risks_blockers = trimmed[:2]
    if not actions_decisions:
        actions_decisions = trimmed[:2]

    return {
        "summary": f"Collected {len(trimmed)} comments and summarized the key discussion, blockers, and actions.",
        "key_points": key_points,
        "risks_blockers": risks_blockers[:3],
        "actions_decisions": actions_decisions[:3],
        "samples": trimmed[:3],
    }
