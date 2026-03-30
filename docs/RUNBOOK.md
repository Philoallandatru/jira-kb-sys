# Runbook

## Environment

Recommended:

- Python 3.10+
- Linux for scheduled runs
- Windows supported for local/manual runs

Optional dependencies by capability:

- `jira`: Jira API crawling via URL + access token
- `markitdown`: PPTX/XLSX/DOCX/PDF conversion
- `weasyprint`: PDF report export
- local OpenAI-compatible LLM service: Qwen answer generation

## Configuration

Copy `.env.example` to `.env` and update:

- Jira credentials
- local LLM API key if required

Edit `config.yaml`:

- `jira.*`
- `docs.*`
- `storage.*`
- `llm.*`
- `reporting.*`

## Demo Workflow

```powershell
$env:PYTHONPATH='.'
python -m app.cli seed-demo
python -m app.cli analyze --date 2026-03-30
python -m app.cli report --date 2026-03-30
streamlit run app/ui.py
```

Then open the Streamlit app and use:

- `Dashboard`
- `Daily Reports`
- `Issue Explorer`
- `Knowledge Hits`
- `Ask Docs`
- `Manage Knowledge`

## Real Document Workflow

```powershell
$env:PYTHONPATH='.'
python -m app.cli import-file "C:\path\to\your.pdf"
python -m app.cli build-docs
python -m app.cli ask "What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?"
```

You can also upload documents directly from Streamlit and click `Rebuild Knowledge Base`.

## Real Jira Workflow

Configure `jira.base_url` and `jira.access_token` first, then:

```powershell
$env:PYTHONPATH='.'
python -m app.cli crawl
python -m app.cli analyze --date YYYY-MM-DD
python -m app.cli report --date YYYY-MM-DD
```

## Output Artifacts

Generated report files are written under:

- `output/daily/YYYY-MM-DD/report.md`
- `output/daily/YYYY-MM-DD/report.json`
- `output/daily/YYYY-MM-DD/report.html`
- `output/daily/YYYY-MM-DD/report.pdf` when WeasyPrint is installed

## Troubleshooting

### `build-docs` works for PDF but not PPTX/XLSX

`MarkItDown` is not installed in the current environment.

### `ask` returns `mode: fallback`

The configured OpenAI-compatible endpoint is not reachable. Retrieval still works; model-backed summarization does not.

### `report` does not create PDF

`WeasyPrint` is not installed. HTML output should still be present.

### `crawl` fails immediately

The Jira Python client is missing, `jira.access_token` is invalid, or the configured JQL is invalid.

## Recommended Next Steps

- Replace BM25-only retrieval with hybrid retrieval if semantic recall becomes a problem
- Tighten NVMe spec heading cleanup if chapter-level precision matters
- Add scheduled execution on Linux through cron or systemd timers
- Connect a real GitHub repository and push the project
