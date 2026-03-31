"use client";

import { useEffect, useState } from "react";
import {
  getIssueDeepAnalysis,
  getIssueDetail,
  listIssues,
  type IssueDeepAnalysisResponse,
  type IssueDetailResponse,
  type IssueItem,
} from "@/lib/api";

const statusOptions = ["Open", "In Progress", "Blocked", "Done", "Closed", "Resolved"];

export function IssuesClient() {
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("All");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [items, setItems] = useState<IssueItem[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<string>("");
  const [detail, setDetail] = useState<IssueDetailResponse | null>(null);
  const [deepAnalysis, setDeepAnalysis] = useState<IssueDeepAnalysisResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingDeepAnalysis, setLoadingDeepAnalysis] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingList(true);
    setError(null);
    listIssues({
      team: team === "All" ? null : team,
      jira_status: statuses,
      query: query || undefined,
    })
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        if (result.items[0] && !selectedIssue) {
          setSelectedIssue(result.items[0].issue_key);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Issue 列表加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingList(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [query, statuses, team]);

  useEffect(() => {
    if (!selectedIssue) return;
    let cancelled = false;
    setLoadingDetail(true);
    setDeepAnalysis(null);
    getIssueDetail(selectedIssue)
      .then((result) => {
        if (!cancelled) {
          setDetail(result);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Issue 详情加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingDetail(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedIssue]);

  async function handleDeepAnalysis() {
    if (!selectedIssue) return;
    setLoadingDeepAnalysis(true);
    setError(null);
    try {
      const result = await getIssueDeepAnalysis(selectedIssue);
      setDeepAnalysis(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "深度分析失败");
    } finally {
      setLoadingDeepAnalysis(false);
    }
  }

  return (
    <div className="issues-layout">
      <aside className="panel">
        <h2>筛选与列表</h2>
        <div className="field">
          <label htmlFor="issue-query">搜索</label>
          <input id="issue-query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="issue key / summary" />
        </div>
        <div className="field">
          <label htmlFor="issue-team">团队</label>
          <select id="issue-team" value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="All">All</option>
            <option value="SV">SV</option>
            <option value="DV">DV</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="issue-status">状态</label>
          <select
            id="issue-status"
            multiple
            value={statuses}
            onChange={(e) => setStatuses(Array.from(e.target.selectedOptions, (option) => option.value))}
            style={{ minHeight: 140 }}
          >
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
        {loadingList && <div className="empty-state">正在加载 Issue 列表。</div>}
        {!loadingList && (
          <div className="stack-list">
            {items.map((item) => (
              <button
                key={item.issue_key}
                className={`list-button ${selectedIssue === item.issue_key ? "active" : ""}`}
                onClick={() => setSelectedIssue(item.issue_key)}
                type="button"
              >
                <strong>{item.issue_key}</strong>
                <span>{item.status}</span>
                <span>{item.summary}</span>
              </button>
            ))}
          </div>
        )}
      </aside>

      <section className="panel">
        <h2>Issue Detail</h2>
        {error && <div className="empty-state">{error}</div>}
        {loadingDetail && <div className="empty-state">正在加载 Issue 详情。</div>}
        {!loadingDetail && detail && (
          <>
            <div className="status-line">
              {detail.issue.issue_key} · {detail.issue.status} · {detail.issue.team ?? "UNKNOWN"}
            </div>
            <div className="summary-section">
              <h3>基础信息</h3>
              <p>{detail.issue.summary}</p>
              <p>Owner: {detail.issue.assignee ?? "-"}</p>
              <p>Priority: {detail.issue.priority ?? "-"}</p>
              <p>Description: {detail.issue.description || "暂无描述"}</p>
            </div>

            {detail.issue_analysis && (
              <>
                <SummarySection title="已有分析" items={[detail.issue_analysis.suspected_root_cause]} />
                <SummarySection title="建议动作" items={detail.issue_analysis.action_needed} />
              </>
            )}

            <SummarySection title="最近变化" items={detail.deltas.map((item) => `${item.change_type} | ${item.details}`)} />

            <div className="summary-section">
              <button className="primary-button" type="button" onClick={handleDeepAnalysis} disabled={loadingDeepAnalysis}>
                {loadingDeepAnalysis ? "生成中..." : "生成单 Jira 深度分析"}
              </button>
            </div>

            {deepAnalysis && (
              <>
                <SummarySection title="Issue Summary" items={[deepAnalysis.result.issue_summary]} />
                <SummarySection title="Spec Relations" items={deepAnalysis.result.spec_relations} />
                <SummarySection title="Policy Relations" items={deepAnalysis.result.policy_relations} />
                <SummarySection title="Related Jira Designs" items={deepAnalysis.result.related_jira_designs} />
                <SummarySection title="Suspected Problems" items={deepAnalysis.result.suspected_problems} />
                <SummarySection title="Next Actions" items={deepAnalysis.result.next_actions} />
                <SummarySection title="Open Questions" items={deepAnalysis.result.open_questions} />
                <SummarySection
                  title="Citations"
                  items={deepAnalysis.result.citations.map(
                    (item) => `${item.source_type} | ${item.summary} | ${item.source_path}`
                  )}
                />
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function SummarySection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="summary-section">
      <h3>{title}</h3>
      <ul className="summary-list">
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
