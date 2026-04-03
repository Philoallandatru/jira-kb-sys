"use client";

import type { DailyReportDetail } from "@/lib/api";
import { MetricCard } from "@/components/summary/MetricCard";
import { SummaryListSection } from "@/components/summary/SummaryListSection";

export function ReportDetailPanel({ detail }: { detail: DailyReportDetail }) {
  return (
    <>
      <div className="status-line">报告日期 | {detail.report.report_date}</div>
      <div className="summary-section" style={{ marginTop: 16 }}>
        <div className="metric-grid">
          <MetricCard label="总 Jira" value={detail.report.metrics.total_issues} />
          <MetricCard label="新增" value={detail.report.metrics.new_issues} />
          <MetricCard label="关闭" value={detail.report.metrics.closed_issues} />
          <MetricCard label="阻塞" value={detail.report.metrics.blocked_issues} />
          <MetricCard label="陈旧" value={detail.report.metrics.stale_issues} />
        </div>
      </div>

      {detail.daily_analysis && (
        <>
          <SummaryListSection title="总体健康度" items={[detail.daily_analysis.overall_health]} />
          <SummaryListSection title="重点风险" items={detail.daily_analysis.top_risks} />
          <SummaryListSection title="建议动作" items={detail.daily_analysis.recommended_actions} />
        </>
      )}

      <SummaryListSection
        title="优先级 Jira"
        items={detail.report.priority_issues.map(
          (item) => `${item.issue_key} | ${item.status} | ${item.priority ?? "-"} | ${item.summary} | ${item.change_summary}`
        )}
      />

      <SummaryListSection
        title="单 Jira 分析摘录"
        items={detail.issue_analyses.map((item) => `${item.issue_key} | ${item.confidence} | ${item.suspected_root_cause}`)}
      />
    </>
  );
}
