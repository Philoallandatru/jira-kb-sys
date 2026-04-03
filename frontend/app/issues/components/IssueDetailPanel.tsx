"use client";

import type { IssueDeepAnalysisResponse, IssueDetailResponse } from "@/lib/api";
import { IssueMetric } from "./IssueMetric";
import { IssueSummarySection } from "./IssueSummarySection";

type IssueDetailPanelProps = {
  detail: IssueDetailResponse | null;
  deepAnalysis: IssueDeepAnalysisResponse | null;
  error: string | null;
  loadingDetail: boolean;
  loadingDeepAnalysis: boolean;
  onDeepAnalysis: () => void;
};

export function IssueDetailPanel({
  detail,
  deepAnalysis,
  error,
  loadingDetail,
  loadingDeepAnalysis,
  onDeepAnalysis,
}: IssueDetailPanelProps) {
  return (
    <>
      <h2>Issue 详情</h2>
      {error && <div className="empty-state">{error}</div>}
      {loadingDetail && <div className="empty-state">正在加载 Issue 详情...</div>}
      {!loadingDetail && !detail && <div className="empty-state">选择左侧 Issue 查看详情。</div>}
      {!loadingDetail && detail && (
        <>
          <div className="status-line">
            {detail.issue.issue_key} | {detail.issue.status} | {detail.issue.team ?? "未标注团队"}
          </div>

          <div className="summary-section">
            <h3>基础信息</h3>
            <div className="metric-grid">
              <IssueMetric label="负责人" value={detail.issue.assignee ?? "-"} />
              <IssueMetric label="优先级" value={detail.issue.priority ?? "-"} />
              <IssueMetric label="项目" value={detail.issue.project ?? "-"} />
              <IssueMetric label="来源筛选器" value={detail.issue.source_filter ?? "-"} />
            </div>
            <p style={{ marginTop: 12 }}>{detail.issue.summary}</p>
            <p style={{ whiteSpace: "pre-wrap" }}>{detail.issue.description || "暂无描述"}</p>
          </div>

          <IssueSummarySection title="标签" items={detail.issue.labels.length ? detail.issue.labels : ["无"]} />
          <IssueSummarySection title="组件" items={detail.issue.components.length ? detail.issue.components : ["无"]} />
          <IssueSummarySection
            title="评论原文"
            items={detail.issue.comments.length ? detail.issue.comments : ["暂无评论"]}
          />
          <IssueSummarySection title="关联链接" items={detail.issue.links.length ? detail.issue.links : ["无"]} />

          {detail.issue_analysis && (
            <>
              <IssueSummarySection title="已有分析" items={[detail.issue_analysis.suspected_root_cause]} />
              <IssueSummarySection title="建议动作" items={detail.issue_analysis.action_needed} />
            </>
          )}

          <IssueSummarySection
            title="最近变更"
            items={
              detail.deltas.length
                ? detail.deltas.map((item) => `${item.change_type} | ${item.details}`)
                : ["当前快照无变更记录"]
            }
          />

          <div className="summary-section">
            <button className="primary-button" type="button" onClick={onDeepAnalysis} disabled={loadingDeepAnalysis}>
              {loadingDeepAnalysis ? "正在生成..." : "生成单 Jira 深度分析"}
            </button>
          </div>

          {deepAnalysis && (
            <>
              <IssueSummarySection title="问题摘要" items={[deepAnalysis.result.issue_summary]} />
              <IssueSummarySection title="Spec 关联" items={deepAnalysis.result.spec_relations} />
              <IssueSummarySection title="Policy 关联" items={deepAnalysis.result.policy_relations} />
              <IssueSummarySection title="相关 Jira 设计线索" items={deepAnalysis.result.related_jira_designs} />
              <IssueSummarySection title="评论摘要" items={[deepAnalysis.result.comment_summary || "无"]} />
              <IssueSummarySection title="评论关键讨论点" items={deepAnalysis.result.comment_key_points} />
              <IssueSummarySection title="评论风险与阻塞" items={deepAnalysis.result.comment_risks_blockers} />
              <IssueSummarySection title="评论结论与行动项" items={deepAnalysis.result.comment_actions_decisions} />
              <IssueSummarySection title="疑似问题" items={deepAnalysis.result.suspected_problems} />
              <IssueSummarySection title="下一步动作" items={deepAnalysis.result.next_actions} />
              <IssueSummarySection title="待确认问题" items={deepAnalysis.result.open_questions} />
              <IssueSummarySection
                title="引用证据"
                items={deepAnalysis.result.citations.map(
                  (item) => `${item.source_type} | ${item.summary} | ${item.source_path}`
                )}
              />
            </>
          )}
        </>
      )}
    </>
  );
}
