"use client";

type SyncTasksSectionProps = {
  jiraState: string;
  confluenceState: string;
  syncDate: string;
  syncDateFrom: string;
  syncDateTo: string;
  onSyncDateChange: (value: string) => void;
  onSyncDateFromChange: (value: string) => void;
  onSyncDateToChange: (value: string) => void;
  onProbeJira: () => void;
  onProbeConfluence: () => void;
  onIncrementalSync: () => void;
  onConfluenceSync: () => void;
  onFullSync: () => void;
  onLegacyCrawl: () => void;
};

export function SyncTasksSection({
  jiraState,
  confluenceState,
  syncDate,
  syncDateFrom,
  syncDateTo,
  onSyncDateChange,
  onSyncDateFromChange,
  onSyncDateToChange,
  onProbeJira,
  onProbeConfluence,
  onIncrementalSync,
  onConfluenceSync,
  onFullSync,
  onLegacyCrawl,
}: SyncTasksSectionProps) {
  return (
    <div className="summary-section">
      <h3>同步任务</h3>
      <div className="status-line">Jira: {jiraState}</div>
      <div className="status-line" style={{ marginTop: 8 }}>
        Confluence: {confluenceState}
      </div>
      <div className="field">
        <label htmlFor="task-sync-date">快照日期</label>
        <input id="task-sync-date" type="date" value={syncDate} onChange={(event) => onSyncDateChange(event.target.value)} />
      </div>
      <div className="settings-stack">
        <button className="secondary-button" type="button" onClick={onProbeJira}>
          检查 Jira 连接
        </button>
        <button className="secondary-button" type="button" onClick={onProbeConfluence}>
          检查 Confluence 连接
        </button>
        <button className="primary-button" type="button" onClick={onIncrementalSync}>
          执行增量同步
        </button>
        <button className="secondary-button" type="button" onClick={onConfluenceSync}>
          执行 Confluence 同步
        </button>
        <div className="field">
          <label htmlFor="task-sync-date-from">全量同步起始日期</label>
          <input
            id="task-sync-date-from"
            type="date"
            value={syncDateFrom}
            onChange={(event) => onSyncDateFromChange(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="task-sync-date-to">全量同步结束日期</label>
          <input
            id="task-sync-date-to"
            type="date"
            value={syncDateTo}
            onChange={(event) => onSyncDateToChange(event.target.value)}
          />
        </div>
        <button className="secondary-button" type="button" onClick={onFullSync}>
          执行全量同步
        </button>
        <button className="secondary-button" type="button" onClick={onLegacyCrawl}>
          执行旧版抓取
        </button>
      </div>
    </div>
  );
}
