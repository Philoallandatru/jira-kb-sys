import { ManagementSummaryClient } from "./ManagementSummaryClient";

export default function ManagementSummaryPage() {
  return (
    <main>
      <section className="hero">
        <h1>Management Summary</h1>
        <p>
          面向管理层的结构化 Jira 摘要页面。当前第一版已经能通过 FastAPI 后端生成任务、轮询状态并展示结果。
          后续会继续接入 Dashboard、日报、单 Jira 深度分析和任务中心。
        </p>
      </section>
      <ManagementSummaryClient />
    </main>
  );
}
