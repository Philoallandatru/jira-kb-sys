export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type ManagementSummaryRequest = {
  date_from: string;
  date_to: string;
  team?: string | null;
  jira_status?: string[];
};

export type SyncTaskRequest = {
  snapshot_date?: string;
  date_from?: string;
  date_to?: string;
  config_path?: string | null;
};

export type TaskRun = {
  id: number;
  run_type: string;
  run_date: string;
  status: string;
  details: string | null;
  details_json: unknown;
  attempt_count: number;
  last_error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
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

export type DashboardOverview = {
  snapshot_date: string;
  metrics: {
    total_issues: number;
    new_issues: number;
    closed_issues: number;
    blocked_issues: number;
    stale_issues: number;
    status_counts: Record<string, number>;
  };
  project_summaries: {
    project: string;
    total: number;
    open_count: number;
    closed_count: number;
    blocked_count: number;
  }[];
  priority_issues: {
    issue_key: string;
    summary: string;
    status: string;
    assignee: string | null;
    priority: string | null;
    change_summary: string;
  }[];
  daily_analysis: {
    overall_health: string;
    top_risks: string[];
    suspected_root_causes: string[];
    recommended_actions: string[];
    watch_items: string[];
  } | null;
};

export type DailyReportListItem = {
  report_date: string;
  issue_count: number;
  blocked_count: number;
  high_priority_open_count: number;
  overall_health: string | null;
};

export type DailyReportDetail = {
  report: {
    report_date: string;
    generated_at: string;
    run_id: number | null;
    metrics: DashboardOverview["metrics"];
    project_summaries: DashboardOverview["project_summaries"];
    priority_issues: DashboardOverview["priority_issues"];
  };
  daily_analysis: DashboardOverview["daily_analysis"];
  issue_analyses: {
    issue_key: string;
    summary: string;
    suspected_root_cause: string;
    evidence: string[];
    action_needed: string[];
    confidence: string;
  }[];
};

export type IssueItem = {
  issue_key: string;
  summary: string;
  status: string;
  team: string | null;
  assignee: string | null;
  priority: string | null;
  project: string | null;
  labels: string[];
  components: string[];
  description: string | null;
  comments: string[];
  links: string[];
  updated_at: string | null;
  created_at: string | null;
  source_filter: string | null;
};

export type IssueDetailResponse = {
  snapshot_date: string;
  issue: IssueItem;
  issue_analysis: {
    issue_key: string;
    summary: string;
    suspected_root_cause: string;
    evidence: string[];
    action_needed: string[];
    confidence: string;
  } | null;
  deltas: {
    issue_key: string;
    change_type: string;
    details: string;
  }[];
};

export type IssueDeepAnalysisResponse = {
  snapshot_date: string;
  result: {
    issue_key: string;
    generated_at: string;
    issue_summary: string;
    spec_relations: string[];
    policy_relations: string[];
    related_jira_designs: string[];
    comment_summary: string;
    comment_key_points: string[];
    comment_risks_blockers: string[];
    comment_actions_decisions: string[];
    suspected_problems: string[];
    next_actions: string[];
    open_questions: string[];
    confidence: string;
    citations: {
      source_type: string;
      source_path: string;
      section_path: string[];
      summary: string;
    }[];
  };
};

export type PromptSettings = {
  default_language: string;
  max_output_tokens: number;
  scenario_max_output_tokens: Record<string, number>;
  custom_prompts: Record<string, string>;
};

export type DocsQARequest = {
  question: string;
  top_k?: number;
  config_path?: string | null;
};

export type DocsQAResponse = {
  question: string;
  answer: string;
  citations: {
    source_path: string;
    section_path: string[];
    quote: string;
    score?: number;
  }[];
  mode: string;
  raw_response: string;
};

export type JiraDocsQARequest = DocsQARequest & {
  snapshot_date?: string | null;
};

export type JiraDocsQAResponse = {
  snapshot_date: string;
  question: string;
  answer: string;
  doc_citations: {
    source_path: string;
    section_path: string[];
    quote: string;
    score?: number;
  }[];
  jira_context: {
    issue_key: string;
    summary: string;
    status: string;
    team?: string | null;
    priority?: string | null;
    assignee?: string | null;
    reason: string;
    ai_root_cause?: string;
    ai_actions?: string[];
  }[];
  mode: string;
  raw_response: string;
};

export type JiraConnectionStatus = {
  ok: boolean;
  base_url: string;
  server_title?: string | null;
  version?: string | null;
  deployment_type?: string | null;
  authenticated_user?: string | null;
  project_filter_count: number;
  has_jql: boolean;
};

export type ConfluenceConnectionStatus = {
  ok: boolean;
  base_url: string;
  authenticated_user?: string | null;
  crawl_mode: string;
  space_keys: string[];
  sample_spaces: string[];
};

export type UploadDocsResult = {
  saved_files: string[];
  destination_dir: string;
  supported_extensions: string[];
  message: string;
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed: ${response.status} ${response.statusText} for ${url}${body ? ` | ${body}` : ""}`);
  }
  return (await response.json()) as T;
}

async function apiFormFetch<T>(path: string, body: FormData): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    method: "POST",
    body,
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Request failed: ${response.status} ${response.statusText} for ${url}${text ? ` | ${text}` : ""}`);
  }
  return (await response.json()) as T;
}

export async function createManagementSummaryTask(payload: ManagementSummaryRequest) {
  return apiFetch<{ id: number; status: string }>("/tasks/reports/management-summary", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createIncrementalSyncTask(payload: SyncTaskRequest = {}) {
  return apiFetch<{ id: number; status: string }>("/tasks/sync/incremental", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createFullSyncTask(payload: SyncTaskRequest = {}) {
  return apiFetch<{ id: number; status: string }>("/tasks/sync/full", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createConfluenceSyncTask() {
  return apiFetch<{ id: number; status: string }>("/tasks/sync/confluence", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function createCrawlTask() {
  return apiFetch<{ id: number; status: string }>("/tasks/crawl", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function createBuildDocsTask() {
  return apiFetch<{ id: number; status: string }>("/tasks/build-docs", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function createAnalyzeTask(payload: { report_date?: string }) {
  return apiFetch<{ id: number; status: string }>("/tasks/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createDailyReportTask(payload: { report_date?: string }) {
  return apiFetch<{ id: number; status: string }>("/tasks/report", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadDocs(files: File[]) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return apiFormFetch<UploadDocsResult>("/docs/upload", formData);
}

export async function listTasks(limit = 50) {
  return apiFetch<{ items: TaskRun[] }>(`/tasks?limit=${limit}`);
}

export async function getTask(runId: number) {
  return apiFetch<TaskRun>(`/tasks/${runId}`);
}

export async function checkJiraConnection() {
  return apiFetch<JiraConnectionStatus>("/integrations/jira/health");
}

export async function checkConfluenceConnection() {
  return apiFetch<ConfluenceConnectionStatus>("/integrations/confluence/health");
}

export async function getManagementSummary(taskId: number) {
  return apiFetch<
    | { id: number; status: string; details?: string; result?: never }
    | { id: number; status: string; result: ManagementSummaryResult }
  >(`/reports/management-summary/${taskId}`);
}

export async function getDashboardOverview(params: {
  report_date?: string;
  team?: string | null;
  jira_status?: string[];
}) {
  const query = new URLSearchParams();
  if (params.report_date) query.set("report_date", params.report_date);
  if (params.team) query.set("team", params.team);
  for (const status of params.jira_status ?? []) {
    query.append("jira_status", status);
  }
  return apiFetch<DashboardOverview>(`/dashboard/overview?${query.toString()}`);
}

export async function listDailyReports(limit = 14) {
  return apiFetch<{ items: DailyReportListItem[] }>(`/reports/daily?limit=${limit}`);
}

export async function getDailyReport(reportDate: string, team?: string | null, jiraStatus?: string[]) {
  const query = new URLSearchParams();
  if (team) query.set("team", team);
  for (const status of jiraStatus ?? []) {
    query.append("jira_status", status);
  }
  return apiFetch<DailyReportDetail>(`/reports/daily/${reportDate}?${query.toString()}`);
}

export async function listIssues(params: {
  report_date?: string;
  team?: string | null;
  jira_status?: string[];
  query?: string;
}) {
  const query = new URLSearchParams();
  if (params.report_date) query.set("report_date", params.report_date);
  if (params.team) query.set("team", params.team);
  if (params.query) query.set("query", params.query);
  for (const status of params.jira_status ?? []) {
    query.append("jira_status", status);
  }
  return apiFetch<{ snapshot_date: string; items: IssueItem[] }>(`/issues?${query.toString()}`);
}

export async function getIssueDetail(issueKey: string, reportDate?: string) {
  const query = new URLSearchParams();
  if (reportDate) query.set("report_date", reportDate);
  return apiFetch<IssueDetailResponse>(`/issues/${encodeURIComponent(issueKey)}?${query.toString()}`);
}

export async function getIssueDeepAnalysis(issueKey: string, reportDate?: string) {
  const query = new URLSearchParams();
  if (reportDate) query.set("report_date", reportDate);
  return apiFetch<IssueDeepAnalysisResponse>(
    `/issues/${encodeURIComponent(issueKey)}/deep-analysis?${query.toString()}`
  );
}

export async function getPromptSettings() {
  return apiFetch<PromptSettings>("/settings/prompts");
}

export async function updatePromptSettings(payload: PromptSettings) {
  return apiFetch<PromptSettings>("/settings/prompts", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function askDocsQuestion(payload: DocsQARequest) {
  return apiFetch<DocsQAResponse>("/qa/docs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function askJiraDocsQuestion(payload: JiraDocsQARequest) {
  return apiFetch<JiraDocsQAResponse>("/qa/jira-docs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
