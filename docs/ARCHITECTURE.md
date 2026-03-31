# 系统架构

## 总览

这个项目当前是一个“Jira + 本地知识库 + 本地大模型”的混合系统，目标是：

- 拉取 Jira 数据
- 生成日报和管理层摘要
- 把本地 spec / policy / design 文档变成可检索知识库
- 用本地模型做工程分析和管理层汇总
- 用 Streamlit 做内部运维台
- 用 FastAPI 作为后续独立前端的后端基础

## 核心链路

### 1. Jira 链路

当前 Jira 链路由这些步骤组成：

1. `crawl`
2. 通过 `jira` Python 客户端访问 Jira
3. 读取 issue 基础字段
4. 保存到 SQLite：
   - `issues_current`
   - `issues_daily_snapshot`
5. 根据前一份 snapshot 生成 `issue_events_derived`

说明：

- 当前还是 snapshot + diff 方案
- 后续若按规划继续推进，会升级成“增量事件拉取 + changelog 历史事件流”

### 2. 文档知识库链路

1. 本地文件进入 `data/raw_docs/`
2. 文档转换为 Markdown
3. Markdown 分块
4. 分块写入：
   - `data/chunks/*.json`
   - SQLite `doc_chunks`
5. 问答或分析时通过 BM25 检索命中文档

当前支持的知识源：

- PDF
- PPTX
- XLSX / XLS
- DOCX
- 后续也可以把 Jira 内容作为知识源入库

### 3. AI 分析链路

当前 AI 侧主要有四类能力：

- 日报级分析
- 单 issue 分析
- 管理层摘要
- 文档问答 / Jira + 文档联合问答

模型调用方式：

- 通过 OpenAI-compatible API
- 默认模型配置在 `config.yaml`
- 默认输出语言为简体中文
- Prompt 已抽象为场景化配置层

### 4. 输出链路

当前输出有这些类型：

- 日报：
  - Markdown
  - JSON
  - HTML
  - PDF（可选）
- 管理层摘要：
  - Markdown
  - JSON
  - HTML
  - PDF（可选）
- 问答结果：
  - CLI 输出
  - Streamlit 页面展示

## 当前模块划分

- `app/config.py`
  - 配置加载
- `app/repository.py`
  - SQLite 表结构和读写
- `app/crawler.py`
  - Jira 抓取和 delta 推导
- `app/docs.py`
  - 文档转换、切块、检索
- `app/analysis.py`
  - 日报和 issue 分析
- `app/management.py`
  - 管理层摘要生成
- `app/qa.py`
  - 文档问答与 Jira + 文档联合问答
- `app/reporting.py`
  - 日报构建和导出
- `app/prompts.py`
  - 场景化 prompt 管理
- `app/ui.py`
  - Streamlit 运维台
- `app/api.py`
  - FastAPI 接口

## 数据存储

### 文件系统

- `data/raw_docs/`
  - 原始文档
- `data/markdown/`
  - 转换后的 Markdown
- `data/chunks/`
  - 文档分块 JSON
- `output/daily/`
  - 日报输出
- `output/management/`
  - 管理层摘要输出

### SQLite 表

- `runs`
- `issues_current`
- `issues_daily_snapshot`
- `issue_events_derived`
- `doc_chunks`
- `ai_analysis_daily`
- `ai_analysis_issue`
- `ai_management_summary`

## 前端形态

### 当前

- Streamlit 负责内部运维台
- FastAPI 只提供少量接口

### 下一步

现在已经可以开始独立前端，因为后端边界已经基本形成：

- 配置层独立
- 仓储层独立
- 管理层摘要服务已独立
- API 已开始成型

推荐下一阶段架构：

- 后端：FastAPI
- 前端：Next.js / React
- Streamlit：继续保留为内部调试和运维界面

## 当前限制

- Jira 仍未升级为完整 changelog 增量事件流
- FastAPI 目前只覆盖管理层摘要接口，还不完整
- Streamlit 仍承担大量主要交互，不适合并发生产使用
- 检索仍以 BM25 为主
- 单 Jira 深度分析还没有独立页面和独立 API
