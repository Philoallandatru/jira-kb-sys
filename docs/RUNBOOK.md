# 运行手册

## 环境要求

- Python 3.10+
- Node.js 20+
- 本地 OpenAI-compatible 模型服务

主要依赖：

- `jira`
- `markitdown`
- `fastapi`
- `uvicorn`
- `streamlit`
- `weasyprint`

## 启动后端

```powershell
$env:PYTHONPATH='.'
uvicorn app.api:app --reload
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

## 启动独立前端

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

## 启动 Streamlit 运维台

```powershell
$env:PYTHONPATH='.'
streamlit run app/ui.py
```

## 常用 CLI

```powershell
$env:PYTHONPATH='.'
python -m app.cli crawl
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
```

## 常用 API

### Dashboard

- `GET /dashboard/overview`

### Daily Reports

- `GET /reports/daily`
- `GET /reports/daily/{report_date}`

### Management Summary

- `POST /tasks/reports/management-summary`
- `GET /reports/management-summary/{run_id}`

### Issues

- `GET /issues`
- `GET /issues/{issue_key}`
- `GET /issues/{issue_key}/deep-analysis`

### QA

- `POST /qa/docs`
- `POST /qa/jira-docs`

### Prompt Settings

- `GET /settings/prompts`
- `PUT /settings/prompts`

## 测试与验证

Python 测试：

```powershell
$env:PYTHONPATH='.'
pytest tests
```

前端构建：

```powershell
cd frontend
npm run build
```

## 常见问题

### 1. `pytest` 找不到 `app`

在 Windows PowerShell 下先设置：

```powershell
$env:PYTHONPATH='.'
```

### 2. 管理层摘要没有 PDF

通常是 `weasyprint` 不可用。Markdown、JSON、HTML 仍会正常生成。

### 3. 前端页面能打开，但请求失败

优先检查：

- `uvicorn app.api:app --reload` 是否已启动
- `NEXT_PUBLIC_API_BASE_URL` 是否正确
- 本地数据库里是否已有 snapshot 数据

### 4. 单 Jira 深度分析为空

优先检查：

- 是否已经执行过 `crawl`
- 是否已经执行过 `build-docs`
- 本地知识库是否包含 spec / policy / design 文档
