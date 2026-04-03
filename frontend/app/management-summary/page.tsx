import { ManagementSummaryClient } from "./ManagementSummaryClient";

export default function ManagementSummaryPage() {
  return (
    <main>
      <section className="hero">
        <h1>项目管理摘要</h1>
        <p>
          面向项目管理的结构化 Jira 摘要页面。当前版本支持通过 FastAPI 任务生成摘要、轮询状态并展示结果，
          也已经与任务中心、日报和单 Jira 深度分析的中文化输出保持一致。
        </p>
      </section>
      <ManagementSummaryClient />
    </main>
  );
}
