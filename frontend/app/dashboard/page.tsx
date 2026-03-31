import { DashboardClient } from "./DashboardClient";

export default function DashboardPage() {
  return (
    <main>
      <section className="hero">
        <h1>Dashboard</h1>
        <p>按当前日期、团队和状态筛选实时查看日报指标、项目分布和高风险 Jira。</p>
      </section>
      <DashboardClient />
    </main>
  );
}
