# 差距分析

## 已完成范围

### 第一阶段

- 中文界面
- 默认中文 Prompt
- 管理层摘要 CLI / API / 前端页面
- 独立前端骨架
- Dashboard 页面
- Daily Reports 页面
- Jira 列表、详情与单 Jira 深度分析页面
- Prompt Settings 页面

### 第二阶段

- `management_summary` 独立场景
- 单 Jira 深度分析独立链路
- Prompt 场景配置与场景级输出长度
- Jira changelog 事件持久化
- Docs QA 与 Jira Docs QA 独立前端页面
- 通用任务中心第一版
- 增量同步 / 全量同步任务入口
- Jira 快照与 AI 分析进入统一知识切块链路
- Jira + Docs 联合检索
- 持久化任务队列与应用内 worker

## 当前已补齐的能力

### 同步与回补

- `POST /tasks/sync/incremental`
- `POST /tasks/sync/full`
- CLI `incremental-sync`
- CLI `full-sync --date-from --date-to`
- full-sync 支持按日期区间回补
- full-sync 使用 changelog 对当前 issue 做历史近似重建

### 知识库与问答

- `build-docs` 同时构建产品文档 chunks 与 Jira knowledge chunks
- Docs QA 只检索产品文档 chunks
- Jira Docs QA 混合检索产品文档 chunks 与 Jira knowledge chunks
- 单 Jira 深度分析只使用产品文档 chunks 做 spec / policy 对照

### 任务执行

- API 任务先入库再执行
- `runs` 持久化保存 payload、开始/结束时间、尝试次数、最后错误
- 应用启动时会回收中断的 `running` 任务
- worker 会自动重试失败任务，默认最多 3 次
- 前端任务中心可查看创建时间、开始时间、结束时间、尝试次数和最后错误

## 仍然存在的边界

### 1. full-sync 不是 Jira 官方历史快照

当前 full-sync 的语义已经从“伪全量”提升成“可回补日期区间”，但它仍然不是 Jira 官方快照源。

限制包括：

- 历史状态依赖当前 issue 数据和 changelog 回放
- 如果 JQL 本身排除了某些老单，这些数据依然回补不回来
- 无法保证对非常早期字段状态做到完全精确复原

### 2. 任务系统仍是单进程 worker

当前已经不是请求绑定的 `BackgroundTasks`，但还不是完整的独立任务系统。

还没做的能力：

- 多 worker 并发调度
- 分布式队列
- 死信队列
- 任务取消
- 任务优先级
- 指数退避或可配置重试策略
- 真正的跨进程执行隔离

### 3. 管理层摘要历史能力仍可增强

当前已经有生成、落库和页面展示，但还没有：

- 历史版本对比
- 多次生成结果 diff
- 摘要版本回溯

## 建议后续顺序

1. 如果要继续补可靠性，优先把任务执行迁移到独立 worker / queue。
2. 如果要继续补数据准确性，优先评估是否能拿到 Jira 官方历史快照来源。
3. 如果要继续补产品能力，优先做 management summary 历史版本对比。
