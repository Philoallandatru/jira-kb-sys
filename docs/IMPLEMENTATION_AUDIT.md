# Jira Summary Web 与搜索增强实现审计

## 1. 审计范围

本次审计核对两类内容：

1. Web 端补齐需求是否已经真正落地。
2. 搜索增强链路是否已经实现并具备测试支撑。

审计基线：

- 仓库路径：`E:\Code\AI\codex\pr-agent\jira-summary`
- 审计时间：`2026-04-03`
- 当前验证结果：`uv run pytest -q -> 36 passed`

## 2. 总体结论

### 2.1 Web 需求

当前状态：`大部分已实现，仍有少量结构化重构未完成`

已完成：

- Jira / Confluence 连通性检查接口已接入前端。
- Confluence 同步任务已接入前端任务中心。
- 本地 policy/spec 文档上传能力已接入前后端。
- 文档上传遵循“只保存，不自动重建索引”的要求。
- 团队主逻辑已从 issue key 前缀切换为 `report_department`。
- 深度分析已纳入评论摘要、关键讨论点、风险阻塞、行动结论。
- 管理摘要相关前后端文案已统一为“项目管理摘要”。
- 主要页面和模板中的中文乱码已清理。

仍未完成：

- `IssuesClient.tsx` 仍是单文件大组件，未进一步拆成卡片级共享组件。
- 任务中心与问题页虽已补齐功能，但视觉和结构层面的组件化重构仍可继续。
- 其他未触达页面是否仍残留旧文案或乱码，尚未做全仓逐页审计。

### 2.2 搜索增强链路

当前状态：`已实现并有测试覆盖`

已落地能力：

- 上下文化 chunk 预处理
- `context_prefix` 与 `retrieval_text`
- `exact_terms` 提取
- BM25 + dense 混合召回
- RRF 融合
- CrossEncoder / heuristic rerank 回退
- query planner
- retrieval telemetry 持久化

## 3. 逐项核对

### 3.1 Confluence 接入 Web

状态：`已实现`

后端：

- `GET /integrations/confluence/health`
- `POST /tasks/sync/confluence`

前端：

- `frontend/lib/api.ts` 已提供：
  - `checkConfluenceConnection()`
  - `createConfluenceSyncTask()`
- `frontend/app/tasks/TaskCenterClient.tsx` 已提供：
  - Confluence 连通性状态展示
  - Confluence 同步按钮
  - 同步结果提示

结论：后端和 Web 闭环已打通。

### 3.2 团队逻辑切换为 `report_department`

状态：`已实现`

已完成改动：

- `app/crawler.py`
  - `_to_issue_record()` 的 `team` 改为取 `report_department`
  - `report_department` 写入 `IssueRecord.report_department`
  - `_extract_change_events()` 的 `team_after` 改为取 `report_department`
  - `_extract_mapped_fields()` 增加逻辑名直读回退，兼容无 field mapping 的测试和导入数据
- `tests/test_team_filter.py` 已改为校验 `report_department` 路径

兼容性补丁：

- `_extract_change_events()` 已兼容 `issue.fields` 缺失的测试 mock，避免因 changelog-only 数据导致异常。

结论：主业务路径已不再依赖 `infer_team_from_issue_key`。

### 3.3 深度分析中文化与评论纳入

状态：`已实现`

后端：

- `app/issue_details.py` 已重写为中文输出。
- 深度分析结构已包含：
  - `comment_summary`
  - `comment_key_points`
  - `comment_risks_blockers`
  - `comment_actions_decisions`
- fallback 分析文本已改为中文。
- 评论关键词抽取已改为中文风险/行动词表。

前端：

- `frontend/lib/api.ts` 已扩展深度分析返回类型。
- `frontend/app/issues/IssuesClient.tsx` 已展示：
  - 评论摘要
  - 评论关键讨论点
  - 评论风险与阻塞
  - 评论结论与行动项

测试：

- `tests/test_issue_details.py` 已覆盖 fallback 评论洞察输出。

结论：评论信息已进入深度分析主链路，并已在页面展示。

### 3.4 页面文案与“项目管理摘要”统一

状态：`已完成本轮触达范围内的统一`

已修改：

- `app/prompts.py`
- `app/management.py`
- `frontend/app/management-summary/ManagementSummaryClient.tsx`
- `frontend/app/management-summary/page.tsx`
- `templates/management_summary.html`

结果：

- “管理层摘要”已统一改为“项目管理摘要”。
- 默认 prompt 与 fallback 文本已切换为中文。

说明：

- 本轮仅保证已修改路径中的文案一致。
- 若需要“全仓所有页面与所有提示词完全统一”，仍需再做一次全量巡检。

### 3.5 Web 上传 policy/spec 文档

状态：`已实现`

后端：

- `POST /docs/upload`
- 支持多文件上传
- 支持扩展名校验
- 支持重复文件名校验
- 支持空文件和超大文件校验
- 上传完成后仅保存文件，不自动执行 `build-docs`

前端：

- `frontend/lib/api.ts` 已提供 `uploadDocs(files)`
- `frontend/app/tasks/TaskCenterClient.tsx` 已提供：
  - 多文件选择
  - 上传动作
  - 上传结果反馈
  - 构建文档索引提示

结论：上传链路前后端均已完成。

### 3.6 局域网访问

状态：`核心能力已完成`

已完成：

- `app/config.py` 默认监听 `0.0.0.0`
- CORS 使用配置化列表
- 前端通过 `NEXT_PUBLIC_API_BASE_URL` 连接后端

结论：服务已具备局域网访问能力。

## 4. 搜索增强实现情况

状态：`已实现`

### 4.1 文档预处理

实现位置：

- `app/retrieval/preprocess.py`
- `app/docs.py`
- `app/jira_knowledge.py`

能力：

- 文档切 chunk
- 生成 `context_prefix`
- 生成 `retrieval_text`
- 提取 `exact_terms`
- 持久化增强后 chunk

### 4.2 混合检索主链路

实现位置：

- `app/retrieval/hybrid.py`
- `app/retrieval/tantivy_index.py`
- `app/retrieval/vector_index.py`
- `app/retrieval/query_planner.py`
- `app/retrieval/rerank.py`

能力：

1. planner 生成检索计划
2. BM25 召回
3. dense 召回
4. RRF 融合
5. CrossEncoder rerank
6. 无 CrossEncoder 时退化到 heuristic rerank

### 4.3 检索追踪

实现位置：

- `app/repository.py`

已持久化：

- `retrieval_runs`
- `retrieval_candidates`

结论：当前系统已具备完整的检索实验与追踪能力。

## 5. 本轮新增实现清单

本轮新增或完成的关键文件：

- `app/crawler.py`
- `app/prompts.py`
- `app/management.py`
- `app/issue_details.py`
- `app/api.py`
- `frontend/lib/api.ts`
- `frontend/app/tasks/TaskCenterClient.tsx`
- `frontend/app/tasks/page.tsx`
- `frontend/app/issues/IssuesClient.tsx`
- `frontend/app/issues/page.tsx`
- `frontend/app/management-summary/ManagementSummaryClient.tsx`
- `frontend/app/management-summary/page.tsx`
- `templates/management_summary.html`
- `tests/test_team_filter.py`
- `tests/test_issue_details.py`

## 6. 验证结果

已执行：

```bash
uv run pytest -q
```

结果：

- `36 passed`

已执行：

```bash
cd frontend
npm run build
```

结果：

- 构建成功

## 7. 后续建议

如果继续往下做，优先级建议如下：

1. 把 `IssuesClient.tsx`、`TaskCenterClient.tsx`、`ManagementSummaryClient.tsx` 继续拆成共享组件，降低页面文件体积。
2. 做一次全仓中文文案与乱码巡检，确认未触达页面、模板、提示词没有遗留旧文本。
3. 清理前端构建产物和无关噪音文件，保持工作区干净。
