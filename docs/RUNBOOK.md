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

## 环境变量

后端本地跨域设置来自 `config.yaml`：

```yaml
server:
  cors_allow_origins:
    - "http://localhost:3000"
    - "http://127.0.0.1:3000"
  cors_allow_credentials: true
```

如果你的前端不是从这两个地址打开，需要把实际前端地址加进去，再重启后端。

后端跨域设置放在 `config.yaml`：

```yaml
server:
  cors_allow_origins:
    - "http://localhost:3000"
    - "http://127.0.0.1:3000"
  cors_allow_credentials: true
```

如果前端不在这两个地址，需要把实际前端 origin 加进去，然后重启后端。

### Windows PowerShell

当前会话：

```powershell
$env:PYTHONPATH='.'
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
```

持久化到用户环境：

```powershell
setx PYTHONPATH "."
setx NEXT_PUBLIC_API_BASE_URL "http://127.0.0.1:8000"
```

### Linux / bash

当前会话：

```bash
export PYTHONPATH=.
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

持久化到 `~/.bashrc`：

```bash
echo 'export PYTHONPATH=.' >> ~/.bashrc
echo 'export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000' >> ~/.bashrc
source ~/.bashrc
```

## 启动后端

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
uvicorn app.api:app --reload
```

### Linux / bash

```bash
export PYTHONPATH=.
uvicorn app.api:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/integrations/jira/health
```

## 启动独立前端

### Windows PowerShell

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
npm run dev
```

### Linux / bash

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm run dev
```

## 启动 Streamlit 运维台

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
streamlit run app/ui.py
```

### Linux / bash

```bash
export PYTHONPATH=.
streamlit run app/ui.py
```

## 常用 CLI

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
python -m app.cli incremental-sync
python -m app.cli full-sync --date-from 2026-03-25 --date-to 2026-03-31
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
```

### Linux / bash

```bash
export PYTHONPATH=.
python -m app.cli incremental-sync
python -m app.cli full-sync --date-from 2026-03-25 --date-to 2026-03-31
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
```

## 常用 API

### 系统与集成

- `GET /health`
- `GET /integrations/jira/health`

### Dashboard

- `GET /dashboard/overview`

### Daily Reports

- `GET /reports/daily`
- `GET /reports/daily/{report_date}`

### Management Summary

- `POST /tasks/reports/management-summary`
- `GET /reports/management-summary/{run_id}`

### Tasks

- `POST /tasks/sync/incremental`
- `POST /tasks/sync/full`
- `POST /tasks/crawl`
- `POST /tasks/build-docs`
- `POST /tasks/analyze`
- `POST /tasks/report`
- `GET /tasks`
- `GET /tasks/{run_id}`

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

### Windows PowerShell

```powershell
$env:PYTHONPATH='.'
pytest tests
python -m compileall app
cd frontend
npm run build
```

### Linux / bash

```bash
export PYTHONPATH=.
pytest tests
python -m compileall app
cd frontend
npm run build
```

## 常见问题

### 1. `pytest` 找不到 `app`

Windows PowerShell：

```powershell
$env:PYTHONPATH='.'
```

Linux / bash：

```bash
export PYTHONPATH=.
```

### 2. 管理层摘要没有 PDF

通常是 `weasyprint` 不可用。Markdown、JSON、HTML 仍会正常生成。

### 3. 前端页面能打开，但请求失败

优先检查：

- `uvicorn app.api:app --reload` 是否已启动
- `NEXT_PUBLIC_API_BASE_URL` 是否正确
- 修改前端环境变量后是否重新启动前端
- `GET /integrations/jira/health` 是否可访问

如果浏览器里看到 `//%3A/tasks/...` 这类 URL，说明前端 API base URL 配错了。
如果浏览器里看到 `OPTIONS /tasks/... 405`，说明 CORS 预检没有通过，通常是后端没有重启到带 CORS 中间件的新版本，或者 `server.cors_allow_origins` 没包含当前前端地址。
如果浏览器里看到 `OPTIONS /tasks/... 405`，说明后端还没启用最新 CORS 配置，或者修改后没有重启。

### 4. 单 Jira 深度分析为空

优先检查：

- 是否已经执行过 `incremental-sync` 或 `crawl`
- 是否已经执行过 `build-docs`
- 本地知识库是否包含 spec / policy / design 文档
