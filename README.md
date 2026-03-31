# Jira KB 系统

面向 SSD/NVMe 场景的 Jira 汇总、知识库检索与本地 AI 分析系统。

当前仓库已经具备这些能力：

- 通过 `base_url + access_token` 访问 Jira
- 保存 Jira 每日快照，并补充真实 changelog 事件存储
- 将本地 `PDF / PPTX / XLSX / DOCX` 转成 Markdown 并建立知识库
- 生成日报、管理层摘要、文档问答、Jira + 文档联合问答
- 提供单 Jira 深度分析
- 提供 Streamlit 运维台
- 提供 FastAPI 后端
- 提供独立前端 `frontend/`，采用复古现代风格

## 当前产品能力

### 1. Jira 数据

- 保存每日快照到 SQLite
- 保存快照差分事件 `issue_events_derived`
- 保存 Jira changelog 事件 `issue_change_events`
- 支持根据 issue key 前缀推断团队：
  - `[SV]` -> `SV`
  - `[DV]` -> `DV`

### 2. AI 分析

- 日报 AI 分析
- 管理层摘要 `management_summary`
- 单 Jira 深度分析
- 文档问答
- Jira + 文档联合问答

### 3. 独立前端

已接通页面：

- `/`
- `/dashboard`
- `/reports`
- `/management-summary`
- `/issues`
- `/settings`

### 4. Prompt 与输出配置

支持：

- 默认输出语言 `zh-CN`
- 全局 `max_output_tokens`
- 场景级 `scenario_max_output_tokens`
- 场景级 `custom_prompts`

相关场景：

- `daily_report`
- `issue_deep_analysis`
- `docs_qa`
- `jira_docs_qa`
- `management_summary`

## 主要目录

- [app](/E:/Code/AI/codex/pr-agent/jira-summary/app)
  Python 后端、CLI、服务层、Streamlit UI
- [frontend](/E:/Code/AI/codex/pr-agent/jira-summary/frontend)
  Next.js 独立前端
- [docs](/E:/Code/AI/codex/pr-agent/jira-summary/docs)
  中文架构、运行与差距说明
- [tests](/E:/Code/AI/codex/pr-agent/jira-summary/tests)
  回归测试

## 配置示例

`config.yaml`：

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

## 常用命令

```powershell
$env:PYTHONPATH='.'
python -m app.cli crawl
python -m app.cli build-docs
python -m app.cli analyze --date 2026-03-31
python -m app.cli report --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
python -m app.cli ask "What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?"
uvicorn app.api:app --reload
streamlit run app/ui.py
```

独立前端：

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

当前已提供：

- `GET /health`
- `GET /dashboard/overview`
- `GET /reports/daily`
- `GET /reports/daily/{report_date}`
- `POST /tasks/reports/management-summary`
- `GET /reports/management-summary/{run_id}`
- `GET /issues`
- `GET /issues/{issue_key}`
- `GET /issues/{issue_key}/deep-analysis`
- `POST /qa/docs`
- `POST /qa/jira-docs`
- `GET /settings/prompts`
- `PUT /settings/prompts`

## 已知边界

当前仍未完全完成的项见：

- [docs/GAP_ANALYSIS.md](/E:/Code/AI/codex/pr-agent/jira-summary/docs/GAP_ANALYSIS.md)

其中最大的剩余项是：

- Jira 全量/增量同步命令与 Web 任务中心还不完整
- Docs QA 与 Jira + Docs QA 还没有独立前端页面
- 前端还没有通用异步任务中心
