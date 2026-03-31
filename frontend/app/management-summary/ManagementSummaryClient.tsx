"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import {
  createManagementSummaryTask,
  getManagementSummary,
  type ManagementSummaryResult,
} from "@/lib/api";

const statusOptions = ["Open", "In Progress", "Blocked", "Done", "Closed", "Resolved"];

type PollState =
  | { mode: "idle" }
  | { mode: "loading"; taskId?: number }
  | { mode: "error"; message: string; taskId?: number }
  | { mode: "success"; taskId: number; result: ManagementSummaryResult };

export function ManagementSummaryClient() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [team, setTeam] = useState("All");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [state, setState] = useState<PollState>({ mode: "idle" });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const nextStatuses = formData.getAll("jira_status").map(String);
    const payload = {
      date_from: String(formData.get("date_from")),
      date_to: String(formData.get("date_to")),
      team: formData.get("team") === "All" ? null : String(formData.get("team")),
      jira_status: nextStatuses,
    };
    setStatuses(nextStatuses);
    setState({ mode: "loading" });
    try {
      const task = await createManagementSummaryTask(payload);
      setState({ mode: "loading", taskId: task.id });
      const start = Date.now();
      while (Date.now() - start < 30000) {
        const result = await getManagementSummary(task.id);
        if ("result" in result && result.result) {
          setState({ mode: "success", taskId: task.id, result: result.result });
          return;
        }
        if (result.status === "failed") {
          setState({ mode: "error", taskId: task.id, message: result.details || "任务失败" });
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      setState({ mode: "error", taskId: task.id, message: "轮询超时，请稍后重试。" });
    } catch (error) {
      setState({ mode: "error", message: error instanceof Error ? error.message : "未知错误" });
    }
  }

  return (
    <div className="management-layout">
      <aside className="panel">
        <h2>生成条件</h2>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="date_from">Date From</label>
            <input id="date_from" name="date_from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="date_to">Date To</label>
            <input id="date_to" name="date_to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="team">团队</label>
            <select id="team" name="team" value={team} onChange={(e) => setTeam(e.target.value)}>
              <option value="All">All</option>
              <option value="SV">SV</option>
              <option value="DV">DV</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="jira_status">Jira 状态</label>
            <select
              id="jira_status"
              name="jira_status"
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
          <button className="primary-button" type="submit">
            生成管理层摘要
          </button>
        </form>
      </aside>

      <section className="panel">
        <h2>摘要结果</h2>
        {state.mode === "idle" && (
          <div className="empty-state">提交时间范围、团队和状态后，这里会展示结构化管理摘要。</div>
        )}
        {state.mode === "loading" && (
          <div className="empty-state">
            <div className="status-line">任务执行中{state.taskId ? ` · #${state.taskId}` : ""}</div>
            <p style={{ marginTop: 12 }}>正在等待 FastAPI 后端返回摘要结果。</p>
          </div>
        )}
        {state.mode === "error" && (
          <div className="empty-state">
            <div className="status-line">任务失败{state.taskId ? ` · #${state.taskId}` : ""}</div>
            <p style={{ marginTop: 12 }}>{state.message}</p>
          </div>
        )}
        {state.mode === "success" && (
          <ManagementSummaryResultView taskId={state.taskId} result={state.result} />
        )}
      </section>
    </div>
  );
}

function ManagementSummaryResultView({
  taskId,
  result,
}: {
  taskId: number;
  result: ManagementSummaryResult;
}) {
  return (
    <>
      <div className="status-line">任务完成 · #{taskId}</div>
      <div className="summary-section" style={{ marginTop: 16 }}>
        <div className="metric-grid">
          <Metric label="最近更新 Jira" value={result.metrics.updated_issue_count} />
          <Metric label="状态推进" value={result.metrics.status_progress_count} />
          <Metric label="关闭" value={result.metrics.closed_count} />
          <Metric label="重开" value={result.metrics.reopened_count} />
          <Metric label="负责人变化" value={result.metrics.assignee_change_count} />
          <Metric label="阻塞" value={result.metrics.blocked_count} />
        </div>
      </div>

      <SummarySection title="最新进展概览" items={result.latest_progress_overview} />
      <SummarySection title="最近更新中的重点变化" items={result.key_recent_changes} />
      <SummarySection title="当前风险与阻塞" items={result.current_risks_and_blockers} />
      <SummarySection title="根因与模式观察" items={result.root_cause_and_pattern_observations} />
      <SummarySection title="给管理层的建议动作" items={result.recommended_management_actions} />
      <SummarySection title="数据不足" items={result.data_gaps.length ? result.data_gaps : ["无"]} />

      <div className="summary-section">
        <h3>Referenced Issue Keys</h3>
        <p>{result.referenced_issue_keys.join(", ") || "-"}</p>
      </div>
    </>
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
