# Jira KB 系统

一个面向 SSD/NVMe 场景的 Jira 汇总、文档知识库检索和本地 AI 分析系统。

当前系统已经具备这些能力：

- 通过 `base_url + access_token` 使用 `jira` Python 客户端访问 Jira
- 抓取 Jira 快照并生成变更摘要
- 将本地 `PDF / PPTX / XLSX / DOCX` 转成 Markdown 并建立知识库
- 生成日报、管理层摘要、问答结果和 AI 分析结果
- 使用本地 OpenAI-compatible 模型服务进行结构化分析
- 提供 Streamlit 运维台界面
- 提供 FastAPI 管理层摘要接口，作为独立前端的后端起点

## 当前产品能力

### Jira 数据能力

- 通过 `jira.base_url`
- 通过 `jira.access_token`
- 通过 `project_filters` 中的 URL 自动提取 `jql`
- 支持团队识别：
  - `issue_key` 以 `[SV]` 开头时识别为 `SV`
  - `issue_key` 以 `[DV]` 开头时识别为 `DV`

### 文档知识库能力

- 本地文档导入到 `data/raw_docs/`
- 转换后的 Markdown 存到 `data/markdown/`
- 切块结果存到 `data/chunks/`
- 支持本地 BM25 检索
- 支持 PDF 的 `pdftotext` 兜底

### AI 分析能力

- 日报级 AI 分析
- 单 issue 级 AI 分析
- 管理层摘要
- 文档问答
- Jira + 文档联合问答

### 前端与接口

- Streamlit 运维台
- FastAPI 管理层摘要接口
- 当前已经可以开始做独立前端

## 为什么现在可以开始做独立前端

可以开始，原因很明确：

- 后端核心数据层已经存在：SQLite、snapshot、delta、AI 结果都已落库
- 管理层摘要已经有独立的数据模型和导出逻辑
- 已经有 FastAPI API 起点，不需要从零起后端服务
- Prompt 配置、管理层摘要、知识库、问答已经从 UI 层分离到服务层

当前最合理的独立前端切入方式是：

- 后端继续用 `FastAPI`
- 新前端用 `React / Next.js`
- Streamlit 保留为内部运维台，不再作为主产品入口

这意味着现在开始独立前端是低风险的，不需要先推倒当前系统。

## 配置示例

`config.yaml`:

```yaml
jira:
  base_url: "https://jira.example.com"
  access_token: ""
  project_filters:
    - name: "default"
      url: "https://jira.example.com/issues/?jql=project%20%3D%20SSD"
  jql: ""
  max_results: 200
  timeout_seconds: 45

llm:
  base_url: "http://localhost:8000/v1"
  api_key: "dummy"
  model: "qwen3.5-35b"
  timeout_seconds: 120
  default_language: "zh-CN"
  max_output_tokens: 4096
  custom_prompts: {}
```

## 常用命令

```powershell
$env:PYTHONPATH='.'
python -m app.cli crawl
python -m app.cli build-docs
python -m app.cli report --date 2026-03-31
python -m app.cli analyze --date 2026-03-31
python -m app.cli management-summary --date-from 2026-03-25 --date-to 2026-03-31 --team SV --jira-status Blocked
python -m app.cli ask "What does section 5.2 say about the Create I/O Completion Queue command in NVMe over PCIe?"
streamlit run app/ui.py
uvicorn app.api:app --reload
```

## Streamlit 运维台页面

- `Dashboard`
- `Daily Reports`
- `Management Summary`
- `Issue Explorer`
- `Knowledge Hits`
- `Ask Docs`
- `Ask Jira + Docs`
- `Manage Knowledge`

## FastAPI 已提供的接口

- `POST /tasks/reports/management-summary`
- `GET /reports/management-summary/{id}`

这两条接口已经足够作为独立前端第一批页面的后端基础。

## 当前建议的下一步

最值得做的是直接开始独立前端一期：

1. 先搭 `FastAPI + Next.js` 的骨架
2. 先接管理层摘要页面
3. 再接 Dashboard、日报、Jira 列表、单 Jira 详情
4. 最后把问答和知识库管理迁过去

## 注意事项

- 如果本地 OpenAI-compatible 服务不可用，系统会自动退回 fallback 分析
- `WeasyPrint` 不可用时，仍然会生成 HTML 和 Markdown
- 当前检索仍以 BM25 为主，后续可以再升级混合检索
