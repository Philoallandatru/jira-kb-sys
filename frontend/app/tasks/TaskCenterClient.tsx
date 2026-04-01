"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createAnalyzeTask,
  createBuildDocsTask,
  createCrawlTask,
  createDailyReportTask,
  createFullSyncTask,
  createIncrementalSyncTask,
  createManagementSummaryTask,
  getTask,
  listTasks,
  type TaskRun,
} from "@/lib/api";

const statusOptions = ["Open", "In Progress", "Blocked", "Done", "Closed", "Resolved"];

export function TaskCenterClient() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [reportDate, setReportDate] = useState(today);
  const [syncDate, setSyncDate] = useState(today);
  const [syncDateFrom, setSyncDateFrom] = useState(today);
  const [syncDateTo, setSyncDateTo] = useState(today);
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [team, setTeam] = useState("All");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [runs, setRuns] = useState<TaskRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedRun, setSelectedRun] = useState<TaskRun | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [actionState, setActionState] = useState("Ready");
  const [error, setError] = useState<string | null>(null);

  async function refreshRuns(preferredRunId?: number) {
    setLoadingRuns(true);
    try {
      const result = await listTasks();
      setRuns(result.items);
      const nextSelectedId = preferredRunId ?? selectedRunId ?? result.items[0]?.id ?? null;
      setSelectedRunId(nextSelectedId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load task list");
    } finally {
      setLoadingRuns(false);
    }
  }

  useEffect(() => {
    refreshRuns();
  }, []);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      return;
    }
    let cancelled = false;
    getTask(selectedRunId)
      .then((run) => {
        if (!cancelled) {
          setSelectedRun(run);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Failed to load task details");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRunId]);

  useEffect(() => {
    if (!selectedRun || !["queued", "running"].includes(selectedRun.status)) {
      return;
    }
    const timer = window.setTimeout(async () => {
      try {
        const latest = await getTask(selectedRun.id);
        setSelectedRun(latest);
        const result = await listTasks();
        setRuns(result.items);
      } catch {
        return;
      }
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [selectedRun]);

  async function launchTask(taskName: string, runFactory: () => Promise<{ id: number; status: string }>) {
    setError(null);
    setActionState(`Submitting ${taskName}...`);
    try {
      const result = await runFactory();
      setActionState(`${taskName} queued as #${result.id}`);
      await refreshRuns(result.id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : `Failed to submit ${taskName}`);
      setActionState(`${taskName} failed`);
    }
  }

  return (
    <div className="qa-layout">
      <aside className="panel">
        <h2>Launch Tasks</h2>
        <div className="status-line">{actionState}</div>

        <div className="summary-section">
          <h3>Sync Tasks</h3>
          <div className="field">
            <label htmlFor="task-sync-date">Snapshot Date</label>
            <input
              id="task-sync-date"
              type="date"
              value={syncDate}
              onChange={(event) => setSyncDate(event.target.value)}
            />
          </div>
          <div className="settings-stack">
            <button
              className="primary-button"
              type="button"
              onClick={() => launchTask("incremental-sync", () => createIncrementalSyncTask({ snapshot_date: syncDate }))}
            >
              Run Incremental Sync
            </button>
            <div className="field">
              <label htmlFor="task-sync-date-from">Full Sync From</label>
              <input
                id="task-sync-date-from"
                type="date"
                value={syncDateFrom}
                onChange={(event) => setSyncDateFrom(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="task-sync-date-to">Full Sync To</label>
              <input
                id="task-sync-date-to"
                type="date"
                value={syncDateTo}
                onChange={(event) => setSyncDateTo(event.target.value)}
              />
            </div>
            <button
              className="secondary-button"
              type="button"
              onClick={() =>
                launchTask("full-sync", () =>
                  createFullSyncTask({
                    date_from: syncDateFrom,
                    date_to: syncDateTo,
                  })
                )
              }
            >
              Run Full Sync
            </button>
            <button className="secondary-button" type="button" onClick={() => launchTask("crawl", () => createCrawlTask())}>
              Run Legacy Crawl
            </button>
          </div>
        </div>

        <div className="summary-section">
          <h3>Knowledge Tasks</h3>
          <div className="settings-stack">
            <button
              className="secondary-button"
              type="button"
              onClick={() => launchTask("build-docs", () => createBuildDocsTask())}
            >
              Build Docs and Jira Chunks
            </button>
          </div>
        </div>

        <div className="summary-section">
          <h3>Daily Tasks</h3>
          <div className="field">
            <label htmlFor="task-report-date">Report Date</label>
            <input
              id="task-report-date"
              type="date"
              value={reportDate}
              onChange={(event) => setReportDate(event.target.value)}
            />
          </div>
          <div className="settings-stack">
            <button
              className="secondary-button"
              type="button"
              onClick={() => launchTask("analyze", () => createAnalyzeTask({ report_date: reportDate }))}
            >
              Generate Daily Analysis
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => launchTask("report", () => createDailyReportTask({ report_date: reportDate }))}
            >
              Export Daily Report
            </button>
          </div>
        </div>

        <div className="summary-section">
          <h3>Management Summary</h3>
          <div className="field">
            <label htmlFor="task-date-from">Date From</label>
            <input id="task-date-from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="task-date-to">Date To</label>
            <input id="task-date-to" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="task-team">Team</label>
            <select id="task-team" value={team} onChange={(event) => setTeam(event.target.value)}>
              <option value="All">All</option>
              <option value="SV">SV</option>
              <option value="DV">DV</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="task-statuses">Jira Status</label>
            <select
              id="task-statuses"
              multiple
              value={statuses}
              onChange={(event) => setStatuses(Array.from(event.target.selectedOptions, (option) => option.value))}
              style={{ minHeight: 140 }}
            >
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={() =>
              launchTask("management-summary", () =>
                createManagementSummaryTask({
                  date_from: dateFrom,
                  date_to: dateTo,
                  team: team === "All" ? null : team,
                  jira_status: statuses,
                })
              )
            }
          >
            Generate Management Summary
          </button>
        </div>
      </aside>

      <section className="panel">
        <h2>Recent Tasks</h2>
        {error && <div className="empty-state">{error}</div>}
        <div className="summary-section">
          <button className="secondary-button" type="button" onClick={() => refreshRuns()}>
            Refresh Task List
          </button>
        </div>
        {loadingRuns && <div className="empty-state">Loading task history...</div>}
        {!loadingRuns && (
          <div className="issues-layout" style={{ gridTemplateColumns: "320px minmax(0, 1fr)" }}>
            <div className="stack-list">
              {runs.map((run) => (
                <button
                  key={run.id}
                  className={`list-button ${selectedRunId === run.id ? "active" : ""}`}
                  type="button"
                  onClick={() => setSelectedRunId(run.id)}
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
              {!selectedRun && <div className="empty-state">Select a run to inspect its details.</div>}
              {selectedRun && (
                <>
                  <div className="status-line">
                    #{selectedRun.id} | {selectedRun.run_type} | {selectedRun.status}
                  </div>
                  <div className="summary-section">
                    <h3>Meta</h3>
                    <p>Run Date: {selectedRun.run_date}</p>
                    <p>Created At: {selectedRun.created_at}</p>
                    <p>Started At: {selectedRun.started_at || "-"}</p>
                    <p>Finished At: {selectedRun.finished_at || "-"}</p>
                  </div>
                  <div className="summary-section">
                    <h3>Details</h3>
                    {selectedRun.details_json ? (
                      <pre>{JSON.stringify(selectedRun.details_json, null, 2)}</pre>
                    ) : (
                      <p>{selectedRun.details || "-"}</p>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
