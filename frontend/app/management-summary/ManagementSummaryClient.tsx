"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import {
  createManagementSummaryTask,
  getManagementSummary,
  type ManagementSummaryResult,
} from "@/lib/api";
import { ManagementSummaryForm } from "./components/ManagementSummaryForm";
import { ManagementSummaryResultView } from "./components/ManagementSummaryResultView";
import { ManagementSummaryStatus } from "./components/ManagementSummaryStatus";

type PollState =
  | { mode: "idle" }
  | { mode: "loading"; taskId?: number }
  | { mode: "error"; message: string; taskId?: number }
  | { mode: "success"; taskId: number; result: ManagementSummaryResult };

export function ManagementSummaryClient() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [team, setTeam] = useState("");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [state, setState] = useState<PollState>({ mode: "idle" });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const nextStatuses = formData.getAll("jira_status").map(String);
    const payload = {
      date_from: String(formData.get("date_from")),
      date_to: String(formData.get("date_to")),
      team: String(formData.get("team") || "").trim() || null,
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
        <ManagementSummaryForm
          dateFrom={dateFrom}
          dateTo={dateTo}
          team={team}
          statuses={statuses}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
          onTeamChange={setTeam}
          onStatusesChange={setStatuses}
          onSubmit={handleSubmit}
        />
      </aside>

      <section className="panel">
        <h2>摘要结果</h2>
        {state.mode === "success" ? (
          <ManagementSummaryResultView taskId={state.taskId} result={state.result} />
        ) : (
          <ManagementSummaryStatus state={state} />
        )}
      </section>
    </div>
  );
}
