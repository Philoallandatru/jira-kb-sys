"use client";

const statusOptions = ["Open", "In Progress", "Blocked", "Done", "Closed", "Resolved"];

type ManagementSummarySectionProps = {
  dateFrom: string;
  dateTo: string;
  team: string;
  statuses: string[];
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  onTeamChange: (value: string) => void;
  onStatusesChange: (value: string[]) => void;
  onGenerate: () => void;
};

export function ManagementSummarySection({
  dateFrom,
  dateTo,
  team,
  statuses,
  onDateFromChange,
  onDateToChange,
  onTeamChange,
  onStatusesChange,
  onGenerate,
}: ManagementSummarySectionProps) {
  return (
    <div className="summary-section">
      <h3>项目管理摘要</h3>
      <div className="field">
        <label htmlFor="task-date-from">开始日期</label>
        <input id="task-date-from" type="date" value={dateFrom} onChange={(event) => onDateFromChange(event.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="task-date-to">结束日期</label>
        <input id="task-date-to" type="date" value={dateTo} onChange={(event) => onDateToChange(event.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="task-team">团队（Report department）</label>
        <input id="task-team" value={team} onChange={(event) => onTeamChange(event.target.value)} placeholder="留空表示全部团队" />
      </div>
      <div className="field">
        <label htmlFor="task-statuses">Jira 状态</label>
        <select
          id="task-statuses"
          multiple
          value={statuses}
          onChange={(event) => onStatusesChange(Array.from(event.target.selectedOptions, (option) => option.value))}
          style={{ minHeight: 140 }}
        >
          {statusOptions.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
      </div>
      <button className="primary-button" type="button" onClick={onGenerate}>
        生成项目管理摘要
      </button>
    </div>
  );
}
