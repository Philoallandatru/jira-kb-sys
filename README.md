# Jira Summary

Jira Summary is a local-first Jira reporting and knowledge retrieval system. It collects Jira snapshots, stores derived history in SQLite, indexes local documents and Confluence pages into retrievable chunks, and uses an OpenAI-compatible model to generate daily reports, project-management summaries, issue deep analysis, and QA responses.

## Current Capabilities

- Crawl Jira snapshots and changelog events into SQLite
- Backfill historical snapshots by replaying changelog data
- Convert local `PDF / PPTX / XLSX / DOCX / Markdown` sources into chunks
- Crawl Confluence Server pages by space using Basic + Token auth
- Build Jira issue knowledge chunks alongside product and Confluence docs
- Upload local `policy / spec / markdown / office / pdf` files through the Web task center
- Run Docs QA and Jira + Docs QA with hybrid retrieval and reranking
- Generate daily reports, project-management summaries, and issue deep analysis
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

Each chunk now stores both the raw text and the retrieval-time context used by the hybrid search stack:

- `raw_text`
- `context_prefix`
- `retrieval_text`
- `exact_terms`
- `page_title / heading_path / ancestor_titles / labels / authors / comment_snippets`

The SQLite database also persists retrieval telemetry:

- `retrieval_runs`
- `retrieval_candidates`
- `qa_feedback`

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

server:
  host: "0.0.0.0"
  port: 8000
  cors_allow_origins:
    - "http://127.0.0.1:3000"
  cors_allow_origin_regex: "^https?://(localhost|127\\.0\\.0\\.1|10\\.\\d+\\.\\d+\\.\\d+|192\\.168\\.\\d+\\.\\d+|172\\.(1[6-9]|2\\d|3[0-1])\\.\\d+\\.\\d+)(:\\d+)?$"

retrieval:
  backend: "tantivy"
  index_dir: "./data/retrieval"
  bm25_top_k: 50
  dense_top_k: 50
  fused_top_k: 60
  rerank_top_k: 10
  enable_recency_bias: true
  recency_half_life_days: 30

embedding:
  model_name: "BAAI/bge-small-en-v1.5"
  batch_size: 16

reranker:
  model_name: "BAAI/bge-reranker-base"
  max_length: 512
```

Notes:

- Jira custom fields should be configured by real `customfield_xxxxx` ids.
- Confluence currently crawls configured spaces and optionally filters by configured root page URLs.
- Confluence pages are normalized into markdown-ish text before indexing, preserving headings, list items, tables, code blocks, warning/info panels, and short comment summaries.
- `IssueRecord.team` now defaults to the Jira `Report department` raw value.
- The API binds to `0.0.0.0` by default so other machines on the same LAN can reach it.
- The frontend now defaults to a same-origin Next.js proxy at `/api/proxy`, so LAN users do not need to manually replace the backend IP when the frontend and backend run on the same host.
- If FastAPI is not running on the same host as the Next.js frontend server, set `JIRA_SUMMARY_BACKEND_URL` for the frontend process.
- Direct browser access to FastAPI from private-network origins is allowed by default through `server.cors_allow_origin_regex`; manual IP allowlisting is only needed if your network does not match the default private IPv4 ranges or if you want stricter origin control.

## Retrieval Architecture

The default v1 retrieval path is:

`Confluence / local docs / Jira snapshots -> contextual chunks -> BM25 + dense candidate recall -> RRF fusion -> rerank -> vLLM answer generation`

Implementation notes:

- Confluence and local docs use section-aware chunking instead of fixed-length slicing first.
- Every chunk gets a deterministic `context_prefix`, then `retrieval_text = context_prefix + raw_text`.
- BM25 uses field-weighted content with exact-term boosts for issue keys, versions, script names, and error codes.
- The dense stage is local-first and can fall back to lightweight token similarity if dedicated retrieval models are unavailable.
- The rerank stage prefers `sentence-transformers` CrossEncoder models when installed and falls back to local heuristic reranking otherwise.

Install the retrieval extras to enable the stronger local stack:

```bash
pip install -e .[retrieval]
```

## Common Commands

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
python -m app.cli seed-demo
python -m app.cli incremental-sync
python -m app.cli full-sync --date-from 2026-03-25 --date-to 2026-03-31
python -m app.cli sync-confluence
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
python -m app.cli ask "Which Jira item is blocked by reset ordering validation?"
python -m app.api
```

### Linux / bash

```bash
export PYTHONPATH=.
python -m app.cli seed-demo
python -m app.cli incremental-sync
python -m app.cli full-sync --date-from 2026-03-25 --date-to 2026-03-31
python -m app.cli sync-confluence
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
python -m app.cli ask "Which Jira item is blocked by reset ordering validation?"
python -m app.api
```

## Offline Mock Development

If Jira and Confluence are only reachable from an intranet, use the built-in demo dataset during local development.

`seed-demo` writes:

- two Jira snapshot days into SQLite
- matching delta records
- three markdown knowledge chunks into `docs/markdown`

As of `2026-04-03`, the seeded snapshot dates are expected to be:

- `2026-04-02`
- `2026-04-03`

Recommended offline validation flow:

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
python -m app.cli seed-demo
python -m app.cli analyze --date 2026-04-03
python -m app.cli report --date 2026-04-03
python -m app.cli management-summary --date-from 2026-04-02 --date-to 2026-04-03
python -m app.api
cd frontend
npm run dev
```

### Linux / bash

```bash
export PYTHONPATH=.
python -m app.cli seed-demo
python -m app.cli analyze --date 2026-04-03
python -m app.cli report --date 2026-04-03
python -m app.cli management-summary --date-from 2026-04-02 --date-to 2026-04-03
python -m app.api
cd frontend
npm run dev
```

This mode is enough to verify:

- dashboard and issue APIs
- daily report generation
- project-management summary generation
- docs upload and QA endpoints
- frontend integration against the local FastAPI server

If WeasyPrint native libraries are not installed on the development machine, daily report and management summary export will still generate `markdown / json / html`, and only PDF output will be skipped.

## FastAPI Endpoints

- `GET /health`
- `GET /integrations/jira/health`
- `GET /integrations/confluence/health`
- `POST /docs/upload`
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
