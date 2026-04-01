# Jira Summary 系统

一个面向 Jira 日报、管理摘要、知识检索和本地 AI 分析的中文系统。

当前仓库已经具备这些主能力：

- 从 Jira 拉取快照并保存到 SQLite
- 持久化 Jira changelog 事件与派生 delta
- 将本地 `PDF / PPTX / XLSX / DOCX / Markdown` 转成统一知识 chunks
- 将 Jira 快照、单 Jira AI 分析、日报 AI 分析一并写入统一知识库
- 生成日报、管理层摘要、单 Jira 深度分析
- 提供 Docs QA 与 Jira + Docs 联合问答
- 提供 FastAPI 后端、Next.js 前端和 CLI
- 提供持久化任务队列和应用内 worker

## 当前功能

### Jira 数据链路

- 每日快照保存到 `issues_daily_snapshot`
- 当前最新状态保存到 `issues_current`
- 派生 delta 保存到 `issue_events_derived`
- 原始 changelog 事件保存到 `issue_change_events`
- 支持基于 changelog 的日期区间 full-sync / backfill

### AI 与知识库

- 产品文档 chunks 写入 `doc_chunks`
- Jira knowledge chunks 也写入 `doc_chunks`
- Docs QA 只检索产品文档 chunks
- Jira + Docs QA 混合检索产品文档 chunks 与 Jira knowledge chunks

Jira knowledge 的 source type：

- `jira_issue`
- `jira_issue_analysis`
- `jira_daily_analysis`

### 任务系统

所有 API 任务都先入库，再由应用内 worker 拉取执行。

已持久化的任务字段包括：

- `payload_json`
- `attempt_count`
- `last_error`
- `started_at`
- `finished_at`

当前行为：

- 新任务先进入 `queued`
- worker 按顺序 claim 任务并执行
- 进程异常中断后，启动时会把残留的 `running` 任务回收到 `queued`
- 运行失败会自动重试，默认最多 3 次

这让任务不再依赖触发它的那次 HTTP 请求存活。

## 前端页面

当前已接入：

- `/`
- `/dashboard`
- `/reports`
- `/management-summary`
- `/issues`
- `/docs-qa`
- `/jira-docs-qa`
- `/tasks`
- `/settings`

## 常用命令

```powershell
$env:PYTHONPATH='.'
python -m app.cli incremental-sync
python -m app.cli full-sync --date-from 2026-03-25 --date-to 2026-03-31
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
python -m app.cli ask "What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?"
uvicorn app.api:app --reload
streamlit run app/ui.py
```

前端开发：

```powershell
cd frontend
npm install
npm run dev
```

如需指定后端地址：

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

## FastAPI 接口

核心接口包括：

- `GET /health`
- `GET /dashboard/overview`
- `GET /reports/daily`
- `GET /reports/daily/{report_date}`
- `POST /tasks/reports/management-summary`
- `POST /tasks/sync/incremental`
- `POST /tasks/sync/full`
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

## 配置示例

`config.yaml`

```yaml
jira:
  base_url: "https://jira.example.com"
  access_token: ""
  project_filters:
    - name: "default"
      url: "https://jira.example.com/issues/?jql=project%20%3D%20SSD"

llm:
  base_url: "http://localhost:8000/v1"
  api_key: "dummy"
  model: "qwen3.5-35b"
  timeout_seconds: 120
  default_language: "zh-CN"
  max_output_tokens: 4096
  custom_prompts: {}
  scenario_max_output_tokens:
    daily_report: 4096
    issue_deep_analysis: 6144
    docs_qa: 4096
    jira_docs_qa: 6144
    management_summary: 6144
```

## 主要目录

- [app](/E:/Code/AI/codex/pr-agent/jira-summary/app)
  Python 后端、CLI、任务执行、AI 分析
- [frontend](/E:/Code/AI/codex/pr-agent/jira-summary/frontend)
  Next.js 独立前端
- [docs](/E:/Code/AI/codex/pr-agent/jira-summary/docs)
  架构、运行和差距说明
- [tests](/E:/Code/AI/codex/pr-agent/jira-summary/tests)
  回归测试

## 仍然存在的边界

当前剩余的主要边界只有两类：

1. full-sync 仍然是基于“当前 issue + changelog”的历史近似回放，不是 Jira 官方历史快照源。
2. 任务系统已经是持久化队列，但仍是单进程应用内 worker，不是独立的分布式 worker / queue。

更细的差距见 [docs/GAP_ANALYSIS.md](/E:/Code/AI/codex/pr-agent/jira-summary/docs/GAP_ANALYSIS.md)。
