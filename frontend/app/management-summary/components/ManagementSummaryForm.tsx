"use client";

const statusOptions = ["Open", "In Progress", "Blocked", "Done", "Closed", "Resolved"];

type ManagementSummaryFormProps = {
  dateFrom: string;
  dateTo: string;
  team: string;
  statuses: string[];
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  onTeamChange: (value: string) => void;
  onStatusesChange: (value: string[]) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
};

export function ManagementSummaryForm({
  dateFrom,
  dateTo,
  team,
  statuses,
  onDateFromChange,
  onDateToChange,
  onTeamChange,
  onStatusesChange,
  onSubmit,
}: ManagementSummaryFormProps) {
  return (
    <>
      <h2>生成条件</h2>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="date_from">开始日期</label>
          <input id="date_from" name="date_from" type="date" value={dateFrom} onChange={(e) => onDateFromChange(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="date_to">结束日期</label>
          <input id="date_to" name="date_to" type="date" value={dateTo} onChange={(e) => onDateToChange(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="team">团队（Report department）</label>
          <input id="team" name="team" value={team} onChange={(e) => onTeamChange(e.target.value)} placeholder="留空表示全部团队" />
        </div>
        <div className="field">
          <label htmlFor="jira_status">Jira 状态</label>
          <select
            id="jira_status"
            name="jira_status"
            multiple
            value={statuses}
            onChange={(e) => onStatusesChange(Array.from(e.target.selectedOptions, (option) => option.value))}
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
          生成项目管理摘要
        </button>
      </form>
    </>
  );
}
