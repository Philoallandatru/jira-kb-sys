"use client";

import type { DashboardOverview } from "@/lib/api";
import { MetricCard } from "@/components/summary/MetricCard";
import { SummaryListSection } from "@/components/summary/SummaryListSection";

export function DashboardOverviewPanel({ data }: { data: DashboardOverview }) {
  return (
    <>
      <div className="status-line">快照日期 | {data.snapshot_date}</div>
      <div className="summary-section" style={{ marginTop: 16 }}>
        <div className="metric-grid">
          <MetricCard label="总 Jira" value={data.metrics.total_issues} />
          <MetricCard label="新增" value={data.metrics.new_issues} />
          <MetricCard label="关闭" value={data.metrics.closed_issues} />
          <MetricCard label="阻塞" value={data.metrics.blocked_issues} />
          <MetricCard label="陈旧" value={data.metrics.stale_issues} />
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

      <SummaryListSection
        title="高风险与重点变化"
        items={data.priority_issues.map(
          (item) => `${item.issue_key} | ${item.status} | ${item.priority ?? "-"} | ${item.summary} | ${item.change_summary}`
        )}
      />

      {data.daily_analysis && (
        <div className="summary-section">
          <h3>AI 日报结论</h3>
          <p>总体健康度：{data.daily_analysis.overall_health}</p>
          <SummaryListSection title="重点风险" items={data.daily_analysis.top_risks} />
          <SummaryListSection title="建议动作" items={data.daily_analysis.recommended_actions} />
        </div>
      )}
    </>
  );
}
