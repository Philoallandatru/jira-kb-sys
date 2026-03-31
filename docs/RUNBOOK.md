# 运行手册

## 环境要求

建议环境：

- Python 3.10+
- Linux 适合定时任务和长期运行
- Windows 适合本地开发与手工运行

主要依赖：

- `jira`
  - 通过 URL + access token 访问 Jira
- `markitdown`
  - 文档转 Markdown
- `weasyprint`
  - 导出 PDF
- 本地 OpenAI-compatible 模型服务
  - 例如 Qwen 本地服务
- `fastapi` + `uvicorn`
  - 提供后端接口

## 配置步骤

### 1. 环境变量

复制 `.env.example` 为 `.env`，按需补充环境变量。

### 2. 修改 `config.yaml`

重点配置这些项：

- `jira.*`
- `docs.*`
- `storage.*`
- `llm.*`
- `reporting.*`

重点说明：

- `jira.base_url`
  - Jira 服务地址
- `jira.access_token`
  - Jira token
- `llm.base_url`
  - 本地 OpenAI-compatible 服务地址
- `llm.default_language`
  - 默认输出语言，当前建议保持 `zh-CN`
- `llm.max_output_tokens`
  - 默认最大输出长度

## 常见运行流程

### Demo 演示流程

```powershell
$env:PYTHONPATH='.'
python -m app.cli seed-demo
python -m app.cli analyze --date 2026-03-30
python -m app.cli report --date 2026-03-30
streamlit run app/ui.py
```

### 真实文档流程

```powershell
$env:PYTHONPATH='.'
python -m app.cli import-file "C:\path\to\your.pdf"
python -m app.cli build-docs
python -m app.cli ask "What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?"
```

### 真实 Jira 流程

```powershell
$env:PYTHONPATH='.'
python -m app.cli crawl
python -m app.cli analyze --date YYYY-MM-DD
python -m app.cli report --date YYYY-MM-DD
```

### 管理层摘要流程

```powershell
$env:PYTHONPATH='.'
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
```

### FastAPI 接口运行

```powershell
$env:PYTHONPATH='.'
uvicorn app.api:app --reload
```

当前已提供接口：

- `POST /tasks/reports/management-summary`
- `GET /reports/management-summary/{id}`

## 产物位置

### 日报输出

- `output/daily/YYYY-MM-DD/report.md`
- `output/daily/YYYY-MM-DD/report.json`
- `output/daily/YYYY-MM-DD/report.html`
- `output/daily/YYYY-MM-DD/report.pdf`

### 管理层摘要输出

- `output/management/<date_from>_to_<date_to>/<team>/<status>/summary.md`
- `output/management/<date_from>_to_<date_to>/<team>/<status>/summary.json`
- `output/management/<date_from>_to_<date_to>/<team>/<status>/summary.html`
- `output/management/<date_from>_to_<date_to>/<team>/<status>/summary.pdf`

## Streamlit 当前用途

Streamlit 目前定位为内部运维台，适合：

- 查看 Dashboard
- 查看日报
- 生成管理层摘要
- 检查 issue 列表
- 做文档问答
- 上传知识库文件

它不适合作为未来多用户并发主产品前端。

## 现在能否开始独立前端

可以，已经可以开始。

原因：

- 管理层摘要已经有独立服务层
- FastAPI 已经有第一条正式 API
- Prompt 已独立
- 仓储层已稳定
- Streamlit 已可退化为运维台

建议的独立前端开发顺序：

1. 先搭 FastAPI + Next.js 骨架
2. 优先接管理层摘要页
3. 再接 Dashboard、日报、Jira 列表
4. 再接单 Jira 深度分析
5. 最后接问答和知识库管理

## 故障排查

### `build-docs` 可处理 PDF，但其他文档转换效果差

通常是 `MarkItDown` 相关依赖不足，或当前环境缺失对应解析器。

### `ask` 返回 `fallback`

本地 OpenAI-compatible 服务不可达，系统会自动退回检索回答。

### `report` 或 `management-summary` 没有生成 PDF

大概率是 `WeasyPrint` 不可用，但 HTML 和 Markdown 仍应生成。

### `crawl` 失败

优先检查：

- `jira` 包是否安装
- `jira.access_token` 是否有效
- `project_filters` 里的 URL/JQL 是否正确

## 下一阶段建议

最值得继续做的事情：

1. 把 FastAPI 扩展成完整后端
2. 启动独立前端工程
3. 给单 Jira 深度分析补独立 API
4. 把 Jira 同步从 snapshot + diff 升级成 changelog 增量事件流
