# Runbook

## Requirements

- Python 3.10+
- Node.js 20+
- An OpenAI-compatible chat completion endpoint
- Jira access token
- Confluence Server username + token if Confluence crawling is enabled

Primary Python dependencies:

- `jira`
- `atlassian-python-api`
- `markitdown`
- `fastapi`
- `uvicorn`
- `streamlit`
- `weasyprint`

## Environment Setup

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
```

### Linux / bash

```bash
export PYTHONPATH=.
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

If the frontend runs on another origin, update `server.cors_allow_origins` in `config.yaml` and restart the API.

## Key Config Sections

### Jira

- `jira.base_url`
- `jira.access_token`
- `jira.project_filters` or `jira.jql`
- `jira.field_mapping.*`

Use real Jira field ids for `jira.field_mapping`, for example:

```yaml
jira:
  field_mapping:
    severity: "customfield_10010"
    root_cause: "customfield_10011"
    platform_name: "customfield_10012"
```

### Confluence

```yaml
confluence:
  base_url: "https://confluence.example.com"
  username: "user@example.com"
  access_token: ""
  crawl_mode: "space"
  space_keys: ["SSD"]
  root_page_urls: []
```

## Start Services

### API

#### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
uvicorn app.api:app --reload
```

#### Linux / bash

```bash
export PYTHONPATH=.
uvicorn app.api:app --reload
```

Health checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/integrations/jira/health
curl http://127.0.0.1:8000/integrations/confluence/health
```

### Frontend

#### Windows PowerShell

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
npm run dev
```

#### Linux / bash

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm run dev
```

### Streamlit UI

#### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
streamlit run app/ui.py
```

#### Linux / bash

```bash
export PYTHONPATH=.
streamlit run app/ui.py
```

## Common CLI Workflows

### Incremental Jira Sync

```bash
python -m app.cli incremental-sync
```

### Historical Backfill

```bash
python -m app.cli full-sync --date-from 2026-03-25 --date-to 2026-03-31
```

### Confluence Crawl

```bash
python -m app.cli sync-confluence
```

### Build Retrieval Index

```bash
python -m app.cli build-docs
```

`build-docs` now indexes:

- local documents
- Confluence pages
- Jira knowledge chunks

### Analysis and Reports

```bash
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV
```

## Common API Tasks

- `POST /tasks/sync/incremental`
- `POST /tasks/sync/full`
- `POST /tasks/sync/confluence`
- `POST /tasks/build-docs`
- `POST /tasks/analyze`
- `POST /tasks/report`
- `POST /tasks/reports/management-summary`

Task execution is persisted in the `runs` table and retried automatically up to the configured in-process limit.

## Validation

### Python

```bash
pytest -q
python -m compileall app
```

### Frontend

```bash
cd frontend
npm run build
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'app'`

Set `PYTHONPATH=.`

### Jira health check fails

Validate:

- `jira.base_url`
- `jira.access_token`
- the configured JQL or filter URLs

### Confluence health check fails

Validate:

- `confluence.base_url`
- `confluence.username`
- `confluence.access_token`
- `confluence.space_keys`

### Docs QA returns weak evidence

Make sure you ran:

1. Jira sync
2. Confluence sync if needed
3. `build-docs`

### Issue deep analysis lacks structured context

Check:

- `jira.field_mapping` is populated with real field ids
- Jira descriptions actually contain ADF tables or key/value reproduction fields
- snapshots were rebuilt after field mapping changes
