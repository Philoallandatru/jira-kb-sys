"use client";

import type { TaskRun } from "@/lib/api";

type TaskRunsPanelProps = {
  runs: TaskRun[];
  selectedRunId: number | null;
  selectedRun: TaskRun | null;
  loadingRuns: boolean;
  error: string | null;
  onRefresh: () => void;
  onSelectRun: (id: number) => void;
};

export function TaskRunsPanel({
  runs,
  selectedRunId,
  selectedRun,
  loadingRuns,
  error,
  onRefresh,
  onSelectRun,
}: TaskRunsPanelProps) {
  return (
    <>
      <h2>最近任务</h2>
      {error && <div className="empty-state">{error}</div>}
      <div className="summary-section">
        <button className="secondary-button" type="button" onClick={onRefresh}>
          刷新任务列表
        </button>
      </div>
      {loadingRuns && <div className="empty-state">正在加载任务历史...</div>}
      {!loadingRuns && (
        <div className="issues-layout" style={{ gridTemplateColumns: "320px minmax(0, 1fr)" }}>
          <div className="stack-list">
            {runs.map((run) => (
              <button
                key={run.id}
                className={`list-button ${selectedRunId === run.id ? "active" : ""}`}
                type="button"
                onClick={() => onSelectRun(run.id)}
              >
                <strong>
                  #{run.id} | {run.run_type}
                </strong>
                <span>{run.status}</span>
                <span>{run.run_date}</span>
              </button>
            ))}
          </div>
          <div>
            {!selectedRun && <div className="empty-state">选择左侧任务查看详情。</div>}
            {selectedRun && (
              <>
                <div className="status-line">
                  #{selectedRun.id} | {selectedRun.run_type} | {selectedRun.status}
                </div>
                <div className="summary-section">
                  <h3>任务元信息</h3>
                  <p>运行日期：{selectedRun.run_date}</p>
                  <p>重试次数：{selectedRun.attempt_count}</p>
                  <p>创建时间：{selectedRun.created_at}</p>
                  <p>开始时间：{selectedRun.started_at || "-"}</p>
                  <p>结束时间：{selectedRun.finished_at || "-"}</p>
                  <p>最近错误：{selectedRun.last_error || "-"}</p>
                </div>
                <div className="summary-section">
                  <h3>任务详情</h3>
                  {selectedRun.details_json ? <pre>{JSON.stringify(selectedRun.details_json, null, 2)}</pre> : <p>{selectedRun.details || "-"}</p>}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
