# Architecture

## Overview

This project is a Markdown-first Jira reporting and local knowledge QA system. It combines:

- Jira snapshot collection and daily diffing
- Local document ingestion into Markdown and chunked search
- Report generation in Markdown, JSON, HTML, and optionally PDF
- AI analysis and QA through an OpenAI-compatible local model endpoint
- Streamlit-based visualization, document QA, and knowledge upload

## Main Data Flow

### Jira pipeline

1. `crawl`
2. Save `issues_current` and `issues_daily_snapshot`
3. Derive daily changes into `issue_events_derived`
4. `report`
5. Generate Markdown/JSON/HTML/PDF report artifacts
6. `analyze`
7. Save daily and issue-level AI analysis into SQLite

### Document pipeline

1. `import-file` or Streamlit upload copies a document into `data/raw_docs`
2. `build-docs` converts files into Markdown
3. Markdown is split into chunks
4. Chunks are written to JSON files and persisted into SQLite
5. BM25 retrieval uses persisted chunks at query time

### QA pipeline

1. User asks a question from CLI or Streamlit
2. BM25 retrieves top matching chunks
3. If an OpenAI-compatible endpoint is reachable, the app requests a structured answer with citations
4. Otherwise it returns a retrieval-based fallback answer with citations

## Key Modules

- `app/config.py`: configuration loading
- `app/repository.py`: SQLite schema and persistence
- `app/crawler.py`: Jira Python client based crawler and delta derivation
- `app/docs.py`: document conversion, PDF normalization, chunking, and BM25 search
- `app/analysis.py`: daily and issue-level AI analysis
- `app/qa.py`: ad hoc document QA over the local chunk index
- `app/reporting.py`: daily report assembly and export
- `app/ui.py`: Streamlit dashboard and document QA/upload UI
- `app/demo.py`: self-contained sample data

## Storage Layout

### File system

- `data/raw_docs/`: original imported files
- `data/markdown/`: converted Markdown files
- `data/chunks/`: JSON chunk dumps for each source document
- `output/daily/YYYY-MM-DD/`: report outputs

### SQLite tables

- `runs`
- `issues_current`
- `issues_daily_snapshot`
- `issue_events_derived`
- `doc_chunks`
- `ai_analysis_daily`
- `ai_analysis_issue`

## Current Limitations

- Jira access token and JQL need to be configured correctly for each real Jira instance.
- Standards PDF heading normalization is improved but not document-perfect.
- BM25 retrieval is precise for spec terms but weaker for purely semantic queries.
- Streamlit is intended for lightweight internal use, not a multi-user production app.
