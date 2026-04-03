"use client";

type PollState =
  | { mode: "idle" }
  | { mode: "loading"; taskId?: number }
  | { mode: "error"; message: string; taskId?: number };

export function ManagementSummaryStatus({ state }: { state: PollState }) {
  if (state.mode === "idle") {
    return <div className="empty-state">提交时间范围、团队和状态后，这里会展示结构化项目管理摘要。</div>;
  }

  if (state.mode === "loading") {
    return (
      <div className="empty-state">
        <div className="status-line">任务执行中{state.taskId ? ` | #${state.taskId}` : ""}</div>
        <p style={{ marginTop: 12 }}>正在等待后端返回摘要结果。</p>
      </div>
    );
  }

  return (
    <div className="empty-state">
      <div className="status-line">任务失败{state.taskId ? ` | #${state.taskId}` : ""}</div>
      <p style={{ marginTop: 12 }}>{state.message}</p>
    </div>
  );
}
