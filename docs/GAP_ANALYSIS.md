# Gap Analysis

## Completed Scope

### Product Surface

- FastAPI backend with task endpoints, reporting endpoints, issue APIs, and QA APIs
- Next.js frontend for dashboard, reports, issues, tasks, QA, and settings
- Streamlit compatibility UI retained for local and legacy usage
- Project-management summary workflow exposed through CLI, API, and frontend

### Jira Data Pipeline

- incremental sync
- full-sync over a date range
- current snapshot persistence
- historical snapshot reconstruction from changelog replay
- derived change-event persistence
- structured Jira field extraction into `IssueRecord`

### Document and Retrieval Pipeline

- local document conversion and chunking
- Confluence ingestion by configured spaces
- Jira knowledge chunk generation
- hybrid retrieval with BM25, dense recall, fusion, and rerank fallback behavior
- Docs QA and Jira + Docs QA split into separate flows

### Analysis and Reporting

- daily report generation
- issue deep analysis
- management summary generation
- AI fallback logic when the LLM endpoint is unavailable
- markdown, json, and html export for reports and management summaries

### Runtime and Reliability

- persisted task queue in SQLite
- worker restart recovery for interrupted runs
- retry tracking in `runs`
- local offline validation through `seed-demo`
- graceful degradation when WeasyPrint native libraries are missing

## Current Gaps

### 1. Historical Sync Is Reconstructed, Not Native Snapshot Export

`full-sync` is useful for backfill, but it is still based on replaying changelog data from the currently reachable issue set.

Implications:

- accuracy depends on Jira changelog completeness
- issues filtered out by current JQL are not recoverable through replay
- very old field states may not be perfectly reproducible

### 2. Task Execution Is Still Single-Process

The task model is no longer request-bound, but it is still an in-process worker design.

Missing capabilities:

- multi-worker scheduling
- distributed queue backend
- dead-letter handling
- cancellation
- task priority
- configurable retry backoff
- process isolation for long-running jobs

### 3. Real Integration Validation Is Environment-Bound

The project now supports an offline demo workflow, but real Jira and Confluence validation still depends on an intranet-capable environment.

What this means in practice:

- local development can validate behavior, not real connectivity
- health checks only become meaningful with real credentials and network access
- production-like verification still needs a separately connected environment

### 4. Export Layer Still Has an Optional Dependency Boundary

Daily report and management summary export now succeed without PDF generation, but native PDF output still depends on local WeasyPrint system libraries.

Current behavior:

- `markdown`, `json`, and `html` always write
- `pdf` is skipped if native libraries are unavailable

### 5. Some Compatibility-Layer Copy Is Still Transitional

The compatibility Streamlit page and parts of the export template were stabilized for readability after earlier encoding issues, but they are not yet the final product copy.

Primary files:

- [ui.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/ui.py)
- [management_summary.html](/E:/Code/AI/codex/pr-agent/jira-summary/templates/management_summary.html)

## Recommended Next Order

1. Finalize compatibility-layer and export-template copy.
2. Validate the same workflows in an intranet-connected environment with real Jira and Confluence credentials.
3. If reliability becomes a priority, move task execution to an external queue / worker model.
4. If data accuracy becomes a priority, evaluate whether native historical snapshot sources are available from Jira.

## Practical Conclusion

The codebase is now in a usable local-development state:

- frontend build passes
- full test suite passes
- offline mock validation works end to end

The remaining work is mainly:

- production-environment validation
- wording and polish
- scaling and operational hardening
