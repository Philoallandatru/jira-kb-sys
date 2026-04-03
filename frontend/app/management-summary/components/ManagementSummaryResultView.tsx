"use client";

import type { ManagementSummaryResult } from "@/lib/api";
import { ManagementSummaryMetric } from "./ManagementSummaryMetric";
import { ManagementSummarySection } from "./ManagementSummarySection";

export function ManagementSummaryResultView({
  taskId,
  result,
}: {
  taskId: number;
  result: ManagementSummaryResult;
}) {
  return (
    <>
      <div className="status-line">任务完成 | #{taskId}</div>
      <div className="summary-section" style={{ marginTop: 16 }}>
        <div className="metric-grid">
          <ManagementSummaryMetric label="最近更新 Jira" value={result.metrics.updated_issue_count} />
          <ManagementSummaryMetric label="状态推进" value={result.metrics.status_progress_count} />
          <ManagementSummaryMetric label="关闭" value={result.metrics.closed_count} />
          <ManagementSummaryMetric label="重开" value={result.metrics.reopened_count} />
          <ManagementSummaryMetric label="负责人变更" value={result.metrics.assignee_change_count} />
          <ManagementSummaryMetric label="阻塞" value={result.metrics.blocked_count} />
        </div>
      </div>

      <ManagementSummarySection title="最新进展概览" items={result.latest_progress_overview} />
      <ManagementSummarySection title="最近更新中的重点变化" items={result.key_recent_changes} />
      <ManagementSummarySection title="当前风险与阻塞" items={result.current_risks_and_blockers} />
      <ManagementSummarySection title="根因与模式观察" items={result.root_cause_and_pattern_observations} />
      <ManagementSummarySection title="给项目管理的建议动作" items={result.recommended_management_actions} />
      <ManagementSummarySection title="数据不足" items={result.data_gaps.length ? result.data_gaps : ["无"]} />

      <div className="summary-section">
        <h3>引用 Issue Keys</h3>
        <p>{result.referenced_issue_keys.join(", ") || "-"}</p>
      </div>
    </>
  );
}
