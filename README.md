# Jira Summary

Markdown-first Jira daily reporting, SSD/NVMe knowledge retrieval, and local AI analysis system.

## What It Does

- Crawls Jira and stores daily snapshots in SQLite
- Converts local documents into Markdown and searchable chunks
- Builds daily report artifacts in Markdown, JSON, HTML, and optionally PDF
- Calls a local OpenAI-compatible Qwen endpoint for daily analysis and issue-level suggestions
- Provides a Streamlit interface for dashboards, issue browsing, evidence review, document QA, and knowledge upload

## Main Commands

```powershell
$env:PYTHONPATH='.'
python -m app.cli crawl
python -m app.cli build-docs
python -m app.cli report --date 2026-03-30
python -m app.cli analyze --date 2026-03-30
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

For real Jira crawling, set `jira.base_url` and `jira.access_token` in `config.yaml`, and provide either `jira.jql` or filter URLs containing `jql=...`.

## Real Document Import

```powershell
$env:PYTHONPATH='.'
python -m app.cli import-file "C:\Users\10259\Downloads\NVM-Express-Base-Specification-Revision-2.1-2024.08.05-Ratified.pdf"
python -m app.cli build-docs
python -m app.cli ask "What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?"
```

## Streamlit Views

- `Dashboard`
- `Daily Reports`
- `Issue Explorer`
- `Knowledge Hits`
- `Ask Docs`
- `Manage Knowledge`

## Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [Runbook](./docs/RUNBOOK.md)

## Notes

- PDF conversion supports a local `pdftotext` fallback for large spec PDFs.
- The current document QA stack uses BM25 retrieval and is optimized for technical term matching.
- PDF export requires `WeasyPrint`.
- GitHub upload still needs a target repository URL or repository name.
