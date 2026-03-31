# 差距分析

## 已完成

### 第一版范围

- 中文文档
- 默认中文 Prompt
- 管理层摘要 CLI / API / 前端页
- 独立前端骨架
- Dashboard 页面
- Daily Reports 页面
- Jira 列表、详情与单 Jira 深度分析页
- Prompt Settings 页面

### 第二版范围

- `management_summary` 独立场景
- 单 Jira 深度分析独立链路
- Prompt 场景配置与场景级输出长度
- Jira changelog 事件持久化
- 独立前端正式接入多页，不再只有占位页

## 尚未完全完成

### 1. Jira 同步命令体系还不完整

当前已有：

- `crawl`

但还没有明确分成：

- 增量同步命令
- 全量回补命令
- 对应的 Web 任务按钮

### 2. Docs QA 与 Jira + Docs QA 还没有独立前端页面

后端 API 已有：

- `POST /qa/docs`
- `POST /qa/jira-docs`

但前端页面尚未补齐。

### 3. 通用任务中心还没有落地

当前只有管理层摘要走后台任务模型。  
其他能力还没有统一任务中心。

### 4. Jira 作为完整知识源入库仍未完成

当前单 Jira 深度分析会复用已有 Jira 快照和 issue analysis，  
但还没有把 Jira 正式 chunk 化后统一进入 `doc_chunks`。

## 建议的下一步顺序

1. 补 `docs-qa` 与 `jira-docs-qa` 前端页面
2. 增加通用任务中心
3. 把 `crawl` 拆成显式的 incremental / full-sync
4. 将 Jira 正式纳入统一知识库切块链路
