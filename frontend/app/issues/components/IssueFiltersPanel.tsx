"use client";

const statusOptions = ["Open", "In Progress", "Blocked", "Done", "Closed", "Resolved"];

type IssueFiltersPanelProps = {
  query: string;
  team: string;
  statuses: string[];
  teamOptions: string[];
  onQueryChange: (value: string) => void;
  onTeamChange: (value: string) => void;
  onStatusesChange: (value: string[]) => void;
};

export function IssueFiltersPanel({
  query,
  team,
  statuses,
  teamOptions,
  onQueryChange,
  onTeamChange,
  onStatusesChange,
}: IssueFiltersPanelProps) {
  return (
    <>
      <h2>筛选与列表</h2>
      <div className="field">
        <label htmlFor="issue-query">搜索</label>
        <input
          id="issue-query"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="issue key / summary / description"
        />
      </div>
      <div className="field">
        <label htmlFor="issue-team">团队（Report department）</label>
        <select id="issue-team" value={team} onChange={(event) => onTeamChange(event.target.value)}>
          <option value="">全部团队</option>
          {teamOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="issue-status">状态</label>
        <select
          id="issue-status"
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
    </>
  );
}
