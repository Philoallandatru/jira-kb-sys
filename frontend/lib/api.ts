export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type ManagementSummaryRequest = {
  date_from: string;
  date_to: string;
  team?: string | null;
  jira_status?: string[];
};

export type ManagementSummaryResult = {
  summary_id: number | null;
  generated_at: string;
  request: ManagementSummaryRequest;
  metrics: {
    updated_issue_count: number;
    status_progress_count: number;
    closed_count: number;
    reopened_count: number;
    assignee_change_count: number;
    blocked_count: number;
    high_priority_open_count: number;
    team_distribution: Record<string, number>;
    status_distribution: Record<string, number>;
    issues_without_owner: number;
    issues_without_root_cause: number;
    referenced_issue_keys: string[];
  };
  latest_progress_overview: string[];
  key_recent_changes: string[];
  current_risks_and_blockers: string[];
  root_cause_and_pattern_observations: string[];
  recommended_management_actions: string[];
  data_gaps: string[];
  referenced_issue_keys: string[];
  referenced_metrics: Record<string, number | string>;
};

export async function createManagementSummaryTask(payload: ManagementSummaryRequest) {
  const response = await fetch(`${API_BASE_URL}/tasks/reports/management-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`创建任务失败: ${response.status}`);
  }
  return (await response.json()) as { id: number; status: string };
}

export async function getManagementSummary(taskId: number) {
  const response = await fetch(`${API_BASE_URL}/reports/management-summary/${taskId}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`查询任务失败: ${response.status}`);
  }
  return (await response.json()) as
    | { id: number; status: string; details?: string; result?: never }
    | { id: number; status: string; result: ManagementSummaryResult };
}
