# 系统架构

## 总览

当前系统由四层组成：

1. Jira 数据采集层
2. 文档知识库层
3. AI 分析与问答层
4. 前端与接口层

## 1. Jira 数据采集层

核心文件：

- [app/crawler.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/crawler.py)
- [app/repository.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/repository.py)

当前实现：

- 通过 `jira` Python 客户端读取 issue 快照
- 支持连接探测 `GET /integrations/jira/health`
- 每次同步会保存：
  - `issues_current`
  - `issues_daily_snapshot`
  - `issue_events_derived`
  - `issue_change_events`

说明：

- `issue_events_derived` 来自相邻快照 diff
- `issue_change_events` 来自 Jira changelog
- full-sync 会基于当前 issue 和 changelog 做历史近似回放

## 2. 文档知识库层

核心文件：

- [app/docs.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/docs.py)
- [app/jira_knowledge.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/jira_knowledge.py)
- [app/repository.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/repository.py)

当前实现：

- 将本地文档转换为 Markdown
- 将 Markdown 切块后写入 `doc_chunks`
- 将 Jira knowledge 也写入 `doc_chunks`
- 使用 BM25 做本地检索

知识库服务于：

- 日报分析
- 单 Jira 深度分析
- 文档问答
- Jira + 文档联合问答

## 3. AI 分析与问答层

核心文件：

- [app/analysis.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/analysis.py)
- [app/management.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/management.py)
- [app/issue_details.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/issue_details.py)
- [app/qa.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/qa.py)
- [app/prompts.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/prompts.py)

当前场景：

- `daily_report`
- `issue_deep_analysis`
- `docs_qa`
- `jira_docs_qa`
- `management_summary`

Prompt 配置策略：

- 所有输出默认简体中文
- 支持 `custom_prompts`
- 支持 `scenario_max_output_tokens`

## 4. 前端与接口层

### Streamlit

核心文件：

- [app/ui.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/ui.py)

定位：

- 内部运维台
- 人工巡检和调试入口

### FastAPI

核心文件：

- [app/api.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/api.py)

已提供能力：

- Dashboard 数据
- 日报列表与详情
- 管理层摘要任务
- Jira 列表与详情
- 单 Jira 深度分析
- 文档问答
- Jira + 文档联合问答
- Prompt 设置读取与更新
- Jira 连通性检查
- 持久化任务队列 API

### 独立前端

核心目录：

- [frontend](/E:/Code/AI/codex/pr-agent/jira-summary/frontend)

技术栈：

- Next.js
- TypeScript

已接通页面：

- `/dashboard`
- `/reports`
- `/management-summary`
- `/issues`
- `/docs-qa`
- `/jira-docs-qa`
- `/tasks`
- `/settings`

任务页额外能力：

- 查看任务开始/结束时间
- 查看尝试次数
- 查看最后错误
- 检查 Jira 连通性

## 任务执行架构

核心文件：

- [app/api.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/api.py)
- [app/repository.py](/E:/Code/AI/codex/pr-agent/jira-summary/app/repository.py)

当前模型：

- API 请求只负责创建 `queued` 任务
- 应用生命周期中启动一个后台 worker
- worker 从 `runs` 表 claim 任务并执行
- 失败任务支持自动重试
- 服务重启时会回收中断的 `running` 任务

当前还不是分布式任务系统，只是单进程持久化 worker。

## 数据存储

SQLite 主要表：

- `runs`
- `issues_current`
- `issues_daily_snapshot`
- `issue_events_derived`
- `issue_change_events`
- `doc_chunks`
- `ai_analysis_daily`
- `ai_analysis_issue`
- `ai_management_summary`

## 运行环境说明

项目同时支持 Windows PowerShell 和 Linux / bash。

最关键的运行时变量：

- `PYTHONPATH`
- `NEXT_PUBLIC_API_BASE_URL`

具体设置方法见 [docs/RUNBOOK.md](/E:/Code/AI/codex/pr-agent/jira-summary/docs/RUNBOOK.md)。

## 当前仍未完全完成

详细缺口见：

- [docs/GAP_ANALYSIS.md](/E:/Code/AI/codex/pr-agent/jira-summary/docs/GAP_ANALYSIS.md)
