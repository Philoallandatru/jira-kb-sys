# 差距分析

## 已完成

### 第一阶段范围
- 中文界面
- 默认中文 Prompt
- 管理层摘要 CLI / API / 前端页面
- 独立前端骨架
- Dashboard 页面
- Daily Reports 页面
- Jira 列表、详情与单 Jira 深度分析页面
- Prompt Settings 页面

### 第二阶段范围
- `management_summary` 独立场景
- 单 Jira 深度分析独立链路
- Prompt 场景配置与场景级输出长度
- Jira changelog 事件持久化
- 独立前端正式接入多页，而不是只保留占位页
- `docs-qa` 与 `jira-docs-qa` 独立前端页面
- 通用任务中心第一版
- 增量同步 / 全量同步任务入口
- Jira 快照与 AI 分析进入统一知识切块链路

## 当前状态

### 已经补齐的能力
- `POST /tasks/sync/incremental` 与 `POST /tasks/sync/full`
- CLI 命令 `incremental-sync` 与 `full-sync`
- Task Center 前端可直接启动同步、构建知识库、分析和报表任务
- `build-docs` 会同时写入产品文档 chunks 与 Jira knowledge chunks
- Docs QA 已改为只检索产品文档 chunks，避免 Jira 内容污染纯文档问答
- Issue deep analysis 也改为只使用产品文档 chunks 做 spec / policy 对照

### Jira 知识入库策略
- `jira_issue`：Jira 快照本体
- `jira_issue_analysis`：单 Jira AI 分析
- `jira_daily_analysis`：日报级 AI 分析
- 统一写入 `doc_chunks`
- 通过 `jira_` 前缀与普通文档 chunks 隔离

## 剩余差距

### 1. 任务编排仍是轻量级后台任务
- 当前仍基于 FastAPI `BackgroundTasks`
- 还不是独立 worker / queue / scheduler
- 长任务失败重试、并发控制、可观测性仍偏弱

### 2. Jira + Docs QA 还没有直接检索 Jira chunks
- 当前联合问答仍然是：
  - Jira 上下文来自快照和 AI 分析表
  - 文档证据来自产品文档 chunks
- 这保证了 docs-only 检索干净，但没有让 QA 直接引用已 chunk 化的 Jira knowledge

### 3. 管理层摘要结果页仍可继续增强
- 已有独立页面与任务链路
- 但尚未做：
  - 历史摘要对比
  - 摘要版本回溯
  - 多次生成结果 diff

## 建议的后续顺序

1. 把后台任务从 `BackgroundTasks` 升级到独立 worker / queue。
2. 为联合问答增加可控的 Jira chunk 检索层，而不是只用结构化快照上下文。
3. 给 management summary 增加历史版本与差异对比。
