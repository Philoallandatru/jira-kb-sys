# Architecture

## Overview

The system is organized into four layers:

1. Jira ingestion and historical reconstruction
2. Document ingestion and retrieval indexing
3. AI analysis and QA
4. API, task execution, and frontend delivery

## 1. Jira Ingestion

Core files:

- [crawler.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/crawler.py)
- [repository.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/repository.py)

Responsibilities:

- query Jira issues and changelog data
- map standard fields and configured custom fields into structured `IssueRecord`
- derive snapshot deltas
- persist snapshots, current state, and raw change events

Structured extraction now includes:

- issue type, versions, resolution, severity
- report department, root cause, frequency, fail runtime
- description table fields such as firmware version, platform, script, expected and actual result
- comments, issue links, blocks links, mentioned-in links

Description parsing strategy:

1. ADF table extraction
2. key/value text extraction
3. raw description fallback

## 2. Document Ingestion and Retrieval

Core files:

- [docs.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/docs.py)
- [confluence.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/confluence.py)
- [jira_knowledge.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/jira_knowledge.py)

Document sources:

- local documents with source types like `local_pdf`
- Confluence pages with source type `confluence_page`
- Jira-generated knowledge with source types:
  - `jira_issue`
  - `jira_issue_analysis`
  - `jira_daily_analysis`

Flow:

- source content is normalized to Markdown
- Markdown is chunked with overlap
- chunks are written into `doc_chunks`
- BM25 is used for local retrieval

Confluence flow:

- `ConfluenceCrawler` connects with Basic + Token auth
- configured spaces are paginated
- pages are converted from storage HTML into Markdown
- page metadata such as URL, ancestors, page id, and update time are preserved

## 3. AI Analysis and QA

Core files:

- [analysis.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/analysis.py)
- [issue_details.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/issue_details.py)
- [management.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/management.py)
- [qa.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/qa.py)

Scenarios:

- `daily_report`
- `issue_deep_analysis`
- `docs_qa`
- `jira_docs_qa`
- `management_summary`

Analysis behavior:

- retrieval query generation now includes structured Jira fields
- deep analysis builds an explicit issue fact sheet before calling the LLM
- related issue matching is no longer token-only; it considers component, root cause, platform, script, versions, and block targets
- management summary metrics now include distributions for issue type, severity, root cause, report department, and component

Fallback behavior remains in place when the LLM endpoint is unavailable.

## 4. API and Task Execution

Core files:

- [api.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/api.py)
- [cli.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/cli.py)
- [repository.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/repository.py)

Task model:

- API creates queued jobs in `runs`
- a single in-process worker loop claims and executes jobs
- interrupted `running` jobs are re-queued on restart
- failed jobs are retried up to the configured in-process limit

Relevant task types:

- incremental Jira sync
- full Jira sync
- Confluence sync
- build docs
- analyze
- report
- management summary

Integration health checks:

- `GET /integrations/jira/health`
- `GET /integrations/confluence/health`

## Storage

Primary SQLite tables:

- `runs`
- `issues_current`
- `issues_daily_snapshot`
- `issue_events_derived`
- `issue_change_events`
- `doc_chunks`
- `ai_analysis_daily`
- `ai_analysis_issue`
- `ai_management_summary`

Most entity evolution is handled through JSON payload compatibility rather than relational schema expansion. That keeps the system tolerant of new structured Jira fields without requiring table migrations for every field addition.

## Frontend

The Next.js frontend consumes the FastAPI layer and exposes:

- `/dashboard`
- `/reports`
- `/management-summary`
- `/issues`
- `/docs-qa`
- `/jira-docs-qa`
- `/tasks`
- `/settings`

## Current Limitations

- historical reconstruction is still inferred from current issue state plus changelog
- task execution is not distributed
- Confluence subtree crawl is implemented as space crawl plus optional root filtering, not a dedicated child-tree traversal starting from each root page
