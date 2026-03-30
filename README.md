# Jira Summary

Markdown-first Jira daily reporting, SSD/NVMe knowledge retrieval, and local AI analysis system.

## What It Does

- Accesses Jira through `base_url + access_token` using the `jira` Python library
- Stores Jira issue snapshots and derived deltas in SQLite
- Converts local documents into Markdown and searchable chunks
- Builds daily report artifacts in Markdown, JSON, HTML, and optionally PDF
- Calls a local OpenAI-compatible Qwen endpoint for daily analysis and issue-level suggestions
- Provides a Streamlit interface for dashboards, issue browsing, evidence review, document QA, combined Jira+Docs QA, and knowledge upload

## Jira Access

Configure Jira in `config.yaml`:

```yaml
jira:
  base_url: "https://jira.example.com"
  access_token: "your-access-token"
  project_filters:
    - name: "default"
      url: "https://jira.example.com/issues/?jql=project%20%3D%20SSD"
  jql: ""
```

The crawler extracts `jql` from each configured Jira URL and queries Jira through the Python `jira` client.

## Team Field and Filtering

- `issue_key` starting with `[SV]` is treated as an `SV` issue
- `issue_key` starting with `[DV]` is treated as a `DV` issue
- Set `reporting.team_filter` in `config.yaml` to `SV` or `DV` to filter report/analyze runs
- Streamlit also exposes a team filter for interactive browsing, combined QA, and dynamic report/dashboard recalculation

## Main Commands

```powershell
$env:PYTHONPATH='.'
python -m app.cli crawl
python -m app.cli build-docs
python -m app.cli report --date 2026-03-31
python -m app.cli analyze --date 2026-03-31
python -m app.cli ask "What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?"
streamlit run app/ui.py
```

## Demo Mode

```powershell
$env:PYTHONPATH='.'
python -m app.cli seed-demo
python -m app.cli analyze --date 2026-03-30
python -m app.cli report --date 2026-03-30
streamlit run app/ui.py
```

The system falls back to retrieval-only or rule-based answers if the configured OpenAI-compatible endpoint is unavailable.

## Streamlit Views

- `Dashboard`
- `Daily Reports`
- `Issue Explorer`
- `Knowledge Hits`
- `Ask Docs`
- `Ask Jira + Docs`
- `Manage Knowledge`

## Notes

- `Manage Knowledge` supports uploading PDF/PPTX/XLSX/DOCX and rebuilding the local knowledge base
- `Ask Jira + Docs` combines the selected day's Jira snapshot with local document retrieval
- `Dashboard` and `Daily Reports` follow the current Streamlit team filter in real time
- PDF conversion supports a local `pdftotext` fallback for large spec PDFs
