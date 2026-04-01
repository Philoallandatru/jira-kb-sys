# Jira Summary

Jira Summary is a local-first Jira reporting and knowledge retrieval system. It collects Jira snapshots, stores derived history in SQLite, indexes local documents and Confluence pages into retrievable chunks, and uses an OpenAI-compatible model to generate daily reports, management summaries, issue deep analysis, and QA responses.

## Current Capabilities

- Crawl Jira snapshots and changelog events into SQLite
- Backfill historical snapshots by replaying changelog data
- Convert local `PDF / PPTX / XLSX / DOCX / Markdown` sources into chunks
- Crawl Confluence Server pages by space using Basic + Token auth
- Build Jira issue knowledge chunks alongside product and Confluence docs
- Run Docs QA and Jira + Docs QA with BM25 retrieval
- Generate daily reports, management summaries, and issue deep analysis
- Expose FastAPI endpoints, CLI commands, a task queue, and a Next.js frontend

## Data Flow

### Jira

- `issues_daily_snapshot`: per-day snapshot records
- `issues_current`: latest issue state
- `issue_events_derived`: snapshot-to-snapshot deltas
- `issue_change_events`: raw changelog-derived events

### Documents

All retrievable knowledge is written into `doc_chunks`, including:

- local source documents with source types like `local_pdf`
- Confluence pages with source type `confluence_page`
- Jira knowledge with source types:
  - `jira_issue`
  - `jira_issue_analysis`
  - `jira_daily_analysis`

## Structured Jira Fields

Issue records now persist both standard and structured fields, including:

- `issue_type`
- `resolution`
- `fix_versions`
- `affects_versions`
- `severity`
- `report_department`
- `root_cause`
- `frequency`
- `fail_runtime`
- `description_fields`
- `activity_comments`
- `activity_all`
- `issue_links`
- `mentioned_in_links`
- `blocks_links`
- `raw_fields`

`description_fields` is populated from ADF tables first, then key/value text, then raw description fallback.

## Configuration

Example `config.yaml` sections:

```yaml
jira:
  base_url: "https://jira.example.com"
  access_token: ""
  project_filters:
    - name: "default"
      url: "https://jira.example.com/issues/?jql=project%20%3D%20SSD"
  jql: ""
  max_results: 200
  timeout_seconds: 45
  field_mapping:
    severity: "customfield_10010"
    root_cause: "customfield_10011"
    platform_name: "customfield_10012"
    script_name: "customfield_10013"

confluence:
  base_url: "https://confluence.example.com"
  username: "user@example.com"
  access_token: ""
  crawl_mode: "space"
  space_keys: ["SSD"]
  root_page_urls: []
  page_limit: 500
  page_size: 50
  timeout_seconds: 45
```

Notes:

- Jira custom fields should be configured by real `customfield_xxxxx` ids.
- Confluence currently crawls configured spaces and optionally filters by configured root page URLs.

## Common Commands

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
python -m app.cli incremental-sync
python -m app.cli full-sync --date-from 2026-03-25 --date-to 2026-03-31
python -m app.cli sync-confluence
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
python -m app.cli ask "Which Jira item is blocked by reset ordering validation?"
uvicorn app.api:app --reload
```

### Linux / bash

```bash
export PYTHONPATH=.
python -m app.cli incremental-sync
python -m app.cli full-sync --date-from 2026-03-25 --date-to 2026-03-31
python -m app.cli sync-confluence
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
python -m app.cli ask "Which Jira item is blocked by reset ordering validation?"
uvicorn app.api:app --reload
```

## FastAPI Endpoints

- `GET /health`
- `GET /integrations/jira/health`
- `GET /integrations/confluence/health`
- `GET /dashboard/overview`
- `GET /reports/daily`
- `GET /reports/daily/{report_date}`
- `POST /tasks/reports/management-summary`
- `POST /tasks/sync/incremental`
- `POST /tasks/sync/full`
- `POST /tasks/sync/confluence`
- `POST /tasks/crawl`
- `POST /tasks/build-docs`
- `POST /tasks/analyze`
- `POST /tasks/report`
- `GET /tasks`
- `GET /tasks/{run_id}`
- `GET /reports/management-summary/{run_id}`
- `GET /issues`
- `GET /issues/{issue_key}`
- `GET /issues/{issue_key}/deep-analysis`
- `POST /qa/docs`
- `POST /qa/jira-docs`
- `GET /settings/prompts`
- `PUT /settings/prompts`

## Frontend Routes

- `/dashboard`
- `/reports`
- `/management-summary`
- `/issues`
- `/docs-qa`
- `/jira-docs-qa`
- `/tasks`
- `/settings`

## Validation

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
pytest -q
```

### Linux / bash

```bash
export PYTHONPATH=.
pytest -q
```

## Remaining Gaps

- Full sync is still a historical reconstruction from current issues plus changelog, not a true historical snapshot source from Jira.
- The task runner is still an in-process persistent worker, not a distributed queue.
- Confluence root-page filtering works, but crawl behavior is still implemented as space pagination plus subtree filtering rather than a strict child-tree traversal from roots.

See [GAP_ANALYSIS.md](/E:/Code/AI/codex/pr-agent/jira-summary/docs/GAP_ANALYSIS.md) for the broader gap list.
