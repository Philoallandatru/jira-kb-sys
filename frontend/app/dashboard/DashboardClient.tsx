"use client";

import { useEffect, useMemo, useState } from "react";
import { getDashboardOverview, type DashboardOverview } from "@/lib/api";

const statusOptions = ["Open", "In Progress", "Blocked", "Done", "Closed", "Resolved"];

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
        <h2>筛选</h2>
        <div className="field">
          <label htmlFor="dashboard-date">报表日期</label>
          <input id="dashboard-date" type="date" value={reportDate} onChange={(e) => setReportDate(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="dashboard-team">团队</label>
          <select id="dashboard-team" value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="All">All</option>
            <option value="SV">SV</option>
            <option value="DV">DV</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="dashboard-status">状态</label>
          <select
            id="dashboard-status"
            multiple
            value={statuses}
            onChange={(e) => setStatuses(Array.from(e.target.selectedOptions, (option) => option.value))}
            style={{ minHeight: 160 }}
          >
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
      </aside>

      <section className="panel">
        <h2>概览</h2>
        {loading && <div className="empty-state">正在加载 Dashboard 数据。</div>}
        {error && <div className="empty-state">{error}</div>}
        {!loading && !error && data && (
          <>
            <div className="status-line">快照日期 · {data.snapshot_date}</div>
            <div className="summary-section" style={{ marginTop: 16 }}>
              <div className="metric-grid">
                <Metric label="总 Jira" value={data.metrics.total_issues} />
                <Metric label="新增" value={data.metrics.new_issues} />
                <Metric label="关闭" value={data.metrics.closed_issues} />
                <Metric label="阻塞" value={data.metrics.blocked_issues} />
                <Metric label="陈旧" value={data.metrics.stale_issues} />
              </div>
            </div>

            <div className="summary-section">
              <h3>项目分布</h3>
              <div className="table-list">
                {data.project_summaries.map((item) => (
                  <div key={item.project} className="table-row">
                    <strong>{item.project}</strong>
                    <span>total {item.total}</span>
                    <span>open {item.open_count}</span>
                    <span>closed {item.closed_count}</span>
                    <span>blocked {item.blocked_count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="summary-section">
              <h3>高风险与重点变化</h3>
              <ul className="summary-list">
                {data.priority_issues.map((item) => (
                  <li key={item.issue_key}>
                    {item.issue_key} | {item.status} | {item.priority ?? "-"} | {item.summary} | {item.change_summary}
                  </li>
                ))}
              </ul>
            </div>

            {data.daily_analysis && (
              <div className="summary-section">
                <h3>AI 日报结论</h3>
                <p>总体健康度：{data.daily_analysis.overall_health}</p>
                <SummarySection title="重点风险" items={data.daily_analysis.top_risks} />
                <SummarySection title="建议动作" items={data.daily_analysis.recommended_actions} />
              </div>
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

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}
