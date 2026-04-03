"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getIssueDeepAnalysis,
  getIssueDetail,
  listIssues,
  type IssueDeepAnalysisResponse,
  type IssueDetailResponse,
  type IssueItem,
} from "@/lib/api";
import { IssueDetailPanel } from "./components/IssueDetailPanel";
import { IssueFiltersPanel } from "./components/IssueFiltersPanel";
import { IssueList } from "./components/IssueList";

export function IssuesClient() {
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [items, setItems] = useState<IssueItem[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<string>("");
  const [detail, setDetail] = useState<IssueDetailResponse | null>(null);
  const [deepAnalysis, setDeepAnalysis] = useState<IssueDeepAnalysisResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingDeepAnalysis, setLoadingDeepAnalysis] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const teamOptions = useMemo(
    () => Array.from(new Set(items.map((item) => item.team).filter((value): value is string => Boolean(value)))).sort(),
    [items]
  );

  useEffect(() => {
    let cancelled = false;
    setLoadingList(true);
    setError(null);
    listIssues({
      team: team || null,
      jira_status: statuses,
      query: query || undefined,
    })
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        setSelectedIssue((current) => {
          if (current && result.items.some((item) => item.issue_key === current)) {
            return current;
          }
          return result.items[0]?.issue_key ?? "";
        });
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
    if (!selectedIssue) {
      setDetail(null);
      setDeepAnalysis(null);
      return;
    }
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
        <IssueFiltersPanel
          query={query}
          team={team}
          statuses={statuses}
          teamOptions={teamOptions}
          onQueryChange={setQuery}
          onTeamChange={setTeam}
          onStatusesChange={setStatuses}
        />
        <IssueList items={items} selectedIssue={selectedIssue} loading={loadingList} onSelect={setSelectedIssue} />
      </aside>

      <section className="panel">
        <IssueDetailPanel
          detail={detail}
          deepAnalysis={deepAnalysis}
          error={error}
          loadingDetail={loadingDetail}
          loadingDeepAnalysis={loadingDeepAnalysis}
          onDeepAnalysis={handleDeepAnalysis}
        />
      </section>
    </div>
  );
}
