from __future__ import annotations

import json
from collections import Counter

from requests import RequestException

from app.analysis import LLMClient
from app.config import AppConfig
from app.docs import BM25Index, SearchHit
from app.models import DeepAnalysisCitation, IssueAIAnalysis, IssueDeepAnalysisResult, IssueRecord, utc_now_iso
from app.repository import Repository


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

    chunks = repo.load_doc_chunks()
    index = BM25Index(chunks)
    related_hits = index.search(
        " ".join(
            filter(
                None,
                [
                    issue.issue_key,
                    issue.summary,
                    issue.description or "",
                    " ".join(issue.labels),
                    " ".join(issue.components),
                ],
            )
        ),
        top_k=8,
    )
    issue_analyses = {item.issue_key: item for item in repo.load_issue_analyses(resolved_snapshot)}
    related_issues = _related_issues(issue, repo.load_snapshot(resolved_snapshot), issue_analyses)
    try:
        client = LLMClient(config)
        payload = client.chat_json(
            prompt=json.dumps(
                {
                    "issue": issue.to_dict(),
                    "snapshot_date": resolved_snapshot,
                    "matched_documents": [_serialize_hit(hit) for hit in related_hits],
                    "related_issues": related_issues,
                    "existing_issue_analysis": issue_analyses.get(issue.issue_key).to_dict() if issue.issue_key in issue_analyses else None,
                },
                ensure_ascii=False,
                indent=2,
            ),
            schema_hint=(
                '{"issue_summary":"string","spec_relations":["string"],"policy_relations":["string"],'
                '"related_jira_designs":["string"],"suspected_problems":["string"],"next_actions":["string"],'
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
    spec_relations = []
    policy_relations = []
    citations = []
    for hit in hits:
        category = _categorize_hit(hit)
        summary = f"{hit.chunk.doc_title} / {' / '.join(hit.chunk.section_path)}"
        citation = DeepAnalysisCitation(
            source_type=category,
            source_path=hit.chunk.source_path,
            section_path=hit.chunk.section_path,
            summary=summary,
        )
        citations.append(citation)
        note = f"{summary}: {' '.join(hit.chunk.content.split())[:180]}"
        if category == "policy":
            policy_relations.append(note)
        elif category == "spec":
            spec_relations.append(note)
    suspected = []
    if cached_analysis:
        suspected.append(f"已有分析认为可能根因是：{cached_analysis.suspected_root_cause}")
    if "block" in issue.status.lower():
        suspected.append("当前状态仍包含阻塞信号，需要优先确认阻塞解除条件。")
    if not spec_relations:
        spec_relations.append("当前未检索到足够明确的 spec 证据。")
    if not policy_relations:
        policy_relations.append("当前未检索到足够明确的 policy/design 证据。")
    next_actions = list(cached_analysis.action_needed if cached_analysis else [])
    if issue.assignee is None:
        next_actions.append("先明确唯一 owner，再推进根因定位与修复计划。")
    if not next_actions:
        next_actions.append("补充日志、复现路径和 spec/policy 对照结论。")
    open_questions = []
    if issue.priority and issue.priority.lower() in {"highest", "high", "critical", "p0", "p1"}:
        open_questions.append("高优先级问题的发布门禁和回归验证是否已经明确？")
    if not issue.description:
        open_questions.append("Jira 描述较少，是否需要补充复现步骤、影响范围和期望行为？")
    return IssueDeepAnalysisResult(
        issue_key=issue.issue_key,
        generated_at=utc_now_iso(),
        issue_summary=issue.summary,
        spec_relations=spec_relations,
        policy_relations=policy_relations,
        related_jira_designs=[item["issue_key"] + ": " + str(item["summary"]) for item in related_issues[:5]],
        suspected_problems=suspected or ["当前证据不足以形成稳定结论。"],
        next_actions=next_actions,
        open_questions=open_questions or ["是否已经收集到足够的 root cause 证据？"],
        confidence="medium" if hits else "low",
        citations=citations[:6],
        raw_response="offline-fallback",
    )


def _related_issues(
    issue: IssueRecord,
    issues: list[IssueRecord],
    issue_analyses: dict[str, IssueAIAnalysis],
) -> list[dict[str, str | list[str]]]:
    current_tokens = set(_tokenize(" ".join(filter(None, [issue.summary, issue.description or "", " ".join(issue.labels), " ".join(issue.components)]))))
    scored = []
    for candidate in issues:
        if candidate.issue_key == issue.issue_key:
            continue
        candidate_tokens = set(
            _tokenize(" ".join(filter(None, [candidate.summary, candidate.description or "", " ".join(candidate.labels), " ".join(candidate.components)])))
        )
        overlap = len(current_tokens & candidate_tokens)
        if overlap == 0:
            continue
        analysis = issue_analyses.get(candidate.issue_key)
        scored.append(
            (
                overlap,
                {
                    "issue_key": candidate.issue_key,
                    "summary": candidate.summary,
                    "status": candidate.status,
                    "reason": f"token_overlap={overlap}",
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
        "section_path": hit.chunk.section_path,
        "score": hit.score,
        "content": hit.chunk.content,
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
        summary = f"{hit.chunk.doc_title} / {' / '.join(hit.chunk.section_path)}"
        key = (hit.chunk.source_path, tuple(hit.chunk.section_path))
        seen[key] += 1
        if seen[key] > 1:
            continue
        deduped.append(
            DeepAnalysisCitation(
                source_type=_categorize_hit(hit),
                source_path=hit.chunk.source_path,
                section_path=hit.chunk.section_path,
                summary=summary,
            )
        )
    return deduped[:6]


def _tokenize(text: str) -> list[str]:
    return [token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if token]
