"use client";

import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import {
  cancelTask,
  checkConfluenceConnection,
  checkJiraConnection,
  createAnalyzeTask,
  createBuildDocsTask,
  createConfluenceSyncTask,
  createCrawlTask,
  createDailyReportTask,
  createFullSyncTask,
  createIncrementalSyncTask,
  createManagementSummaryTask,
  getTask,
  listTasks,
  type TaskRun,
  uploadDocs,
} from "@/lib/api";
import { DailyTasksSection } from "./components/DailyTasksSection";
import { KnowledgeTasksSection } from "./components/KnowledgeTasksSection";
import { ManagementSummarySection } from "./components/ManagementSummarySection";
import { SyncTasksSection } from "./components/SyncTasksSection";
import { TaskRunsPanel } from "./components/TaskRunsPanel";

export function TaskCenterClient() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [reportDate, setReportDate] = useState(today);
  const [syncDate, setSyncDate] = useState(today);
  const [syncDateFrom, setSyncDateFrom] = useState(today);
  const [syncDateTo, setSyncDateTo] = useState(today);
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [team, setTeam] = useState("");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [runs, setRuns] = useState<TaskRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedRun, setSelectedRun] = useState<TaskRun | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [cancellingRunId, setCancellingRunId] = useState<number | null>(null);
  const [actionState, setActionState] = useState("就绪");
  const [jiraState, setJiraState] = useState("未检查");
  const [confluenceState, setConfluenceState] = useState("未检查");
  const [uploadState, setUploadState] = useState("未上传文档");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshRuns(preferredRunId?: number) {
    setLoadingRuns(true);
    try {
      const result = await listTasks();
      setRuns(result.items);
      const nextSelectedId = preferredRunId ?? selectedRunId ?? result.items[0]?.id ?? null;
      setSelectedRunId(nextSelectedId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "加载任务列表失败");
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
          setError(requestError instanceof Error ? requestError.message : "加载任务详情失败");
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
    setActionState(`正在提交 ${taskName}...`);
    try {
      const result = await runFactory();
      setActionState(`${taskName} 已排队，任务 #${result.id}`);
      await refreshRuns(result.id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : `提交 ${taskName} 失败`);
      setActionState(`${taskName} 提交失败`);
    }
  }

  async function handleCancelRun(runId: number) {
    setError(null);
    setCancellingRunId(runId);
    setActionState(`正在停止任务 #${runId}...`);
    try {
      const result = await cancelTask(runId);
      setActionState(`任务 #${runId} ${result.message}`);
      await refreshRuns(runId);
      const latest = await getTask(runId);
      setSelectedRun(latest);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : `停止任务 #${runId} 失败`);
      setActionState(`停止任务 #${runId} 失败`);
    } finally {
      setCancellingRunId(null);
    }
  }

  async function probeJiraConnection() {
    setError(null);
    setJiraState("正在检查 Jira 连接...");
    try {
      const result = await checkJiraConnection();
      setJiraState(
        `已连接 ${result.base_url}${result.server_title ? ` | ${result.server_title}` : ""}${
          result.authenticated_user ? ` | ${result.authenticated_user}` : ""
        }`
      );
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Jira 连接失败";
      setError(message);
      setJiraState("Jira 连接失败");
    }
  }

  async function probeConfluenceConnection() {
    setError(null);
    setConfluenceState("正在检查 Confluence 连接...");
    try {
      const result = await checkConfluenceConnection();
      setConfluenceState(
        `已连接 ${result.base_url}${result.authenticated_user ? ` | ${result.authenticated_user}` : ""}${
          result.space_keys.length ? ` | Space: ${result.space_keys.join(", ")}` : ""
        }`
      );
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Confluence 连接失败";
      setError(message);
      setConfluenceState("Confluence 连接失败");
    }
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) {
      return;
    }
    setUploading(true);
    setError(null);
    setUploadState("正在上传文档...");
    try {
      const result = await uploadDocs(files);
      setUploadState(`${result.message} 已保存 ${result.saved_files.length} 个文件。`);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "上传文档失败";
      setError(message);
      setUploadState("上传文档失败");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  return (
    <div className="qa-layout">
      <aside className="panel">
        <h2>任务中心</h2>
        <div className="status-line">{actionState}</div>

        <SyncTasksSection
          jiraState={jiraState}
          confluenceState={confluenceState}
          syncDate={syncDate}
          syncDateFrom={syncDateFrom}
          syncDateTo={syncDateTo}
          onSyncDateChange={setSyncDate}
          onSyncDateFromChange={setSyncDateFrom}
          onSyncDateToChange={setSyncDateTo}
          onProbeJira={probeJiraConnection}
          onProbeConfluence={probeConfluenceConnection}
          onIncrementalSync={() => launchTask("增量同步", () => createIncrementalSyncTask({ snapshot_date: syncDate }))}
          onConfluenceSync={() => launchTask("Confluence 同步", () => createConfluenceSyncTask())}
          onFullSync={() =>
            launchTask("全量同步", () =>
              createFullSyncTask({
                date_from: syncDateFrom,
                date_to: syncDateTo,
              })
            )
          }
          onLegacyCrawl={() => launchTask("旧版抓取", () => createCrawlTask())}
        />

        <KnowledgeTasksSection
          uploadState={uploadState}
          uploading={uploading}
          onUpload={handleUpload}
          onBuildDocs={() => launchTask("构建文档索引", () => createBuildDocsTask())}
        />

        <DailyTasksSection
          reportDate={reportDate}
          onReportDateChange={setReportDate}
          onAnalyze={() => launchTask("生成日报分析", () => createAnalyzeTask({ report_date: reportDate }))}
          onExportReport={() => launchTask("导出日报", () => createDailyReportTask({ report_date: reportDate }))}
        />

        <ManagementSummarySection
          dateFrom={dateFrom}
          dateTo={dateTo}
          team={team}
          statuses={statuses}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
          onTeamChange={setTeam}
          onStatusesChange={setStatuses}
          onGenerate={() =>
            launchTask("项目管理摘要", () =>
              createManagementSummaryTask({
                date_from: dateFrom,
                date_to: dateTo,
                team: team.trim() || null,
                jira_status: statuses,
              })
            )
          }
        />
      </aside>

      <section className="panel">
        <TaskRunsPanel
          runs={runs}
          selectedRunId={selectedRunId}
          selectedRun={selectedRun}
          loadingRuns={loadingRuns}
          error={error}
          cancellingRunId={cancellingRunId}
          onRefresh={() => refreshRuns()}
          onSelectRun={setSelectedRunId}
          onCancelRun={handleCancelRun}
        />
      </section>
    </div>
  );
}
