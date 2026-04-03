"use client";

import { useEffect, useMemo, useState } from "react";
import { getDashboardOverview, type DashboardOverview } from "@/lib/api";
import { DashboardFilters } from "./components/DashboardFilters";
import { DashboardOverviewPanel } from "./components/DashboardOverviewPanel";

export function DashboardClient() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [reportDate, setReportDate] = useState(today);
  const [team, setTeam] = useState("All");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDashboardOverview({
      report_date: reportDate,
      team: team === "All" ? null : team,
      jira_status: statuses,
    })
      .then((result) => {
        if (!cancelled) {
          setData(result);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reportDate, statuses, team]);

  return (
    <div className="management-layout">
      <aside className="panel">
        <DashboardFilters
          reportDate={reportDate}
          team={team}
          statuses={statuses}
          onReportDateChange={setReportDate}
          onTeamChange={setTeam}
          onStatusesChange={setStatuses}
        />
      </aside>

      <section className="panel">
        <h2>概览</h2>
        {loading && <div className="empty-state">正在加载 Dashboard 数据。</div>}
        {error && <div className="empty-state">{error}</div>}
        {!loading && !error && data && <DashboardOverviewPanel data={data} />}
      </section>
    </div>
  );
}
