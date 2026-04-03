"use client";

const statusOptions = ["Open", "In Progress", "Blocked", "Done", "Closed", "Resolved"];

type DashboardFiltersProps = {
  reportDate: string;
  team: string;
  statuses: string[];
  onReportDateChange: (value: string) => void;
  onTeamChange: (value: string) => void;
  onStatusesChange: (value: string[]) => void;
};

export function DashboardFilters({
  reportDate,
  team,
  statuses,
  onReportDateChange,
  onTeamChange,
  onStatusesChange,
}: DashboardFiltersProps) {
  return (
    <>
      <h2>筛选</h2>
      <div className="field">
        <label htmlFor="dashboard-date">报告日期</label>
        <input id="dashboard-date" type="date" value={reportDate} onChange={(e) => onReportDateChange(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="dashboard-team">团队</label>
        <select id="dashboard-team" value={team} onChange={(e) => onTeamChange(e.target.value)}>
          <option value="All">All</option>
          <option value="SV">SV</option>
          <option value="DV">DV</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor="dashboard-status">状态</label>
        <select
          id="dashboard-status"
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
    </>
  );
}
