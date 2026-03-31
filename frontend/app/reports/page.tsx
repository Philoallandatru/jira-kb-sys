import { ReportsClient } from "./ReportsClient";

export default function ReportsPage() {
  return (
    <main>
      <section className="hero">
        <h1>Daily Reports</h1>
        <p>浏览历史日报，查看当天指标、AI 摘要和优先级 Jira 明细。</p>
      </section>
      <ReportsClient />
    </main>
  );
}
