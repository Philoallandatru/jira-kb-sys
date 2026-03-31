import Link from "next/link";

const cards = [
  {
    title: "Management Summary",
    description: "面向管理层的结构化摘要，聚焦最近更新的 Jira、风险、趋势、协作效率和闭环质量。",
    href: "/management-summary",
  },
  {
    title: "Dashboard",
    description: "后续接入日报指标、团队过滤、状态趋势和高风险变化总览。",
    href: "/dashboard",
  },
  {
    title: "Daily Reports",
    description: "后续接入日报内容、导出和历史浏览。",
    href: "/reports",
  },
  {
    title: "Issues",
    description: "后续接入 Jira 列表、单 Jira 详情、spec/policy 关联和深度分析。",
    href: "/issues",
  },
];

export default function HomePage() {
  return (
    <main>
      <section className="hero">
        <h1>Retro Modern Control Surface</h1>
        <p>
          这个独立前端是下一阶段的正式入口。当前第一版先打通管理层摘要页面，并保留统一的复古现代视觉语言，
          后续逐步接入 Dashboard、日报、Jira 明细、知识库问答和任务中心。
        </p>
      </section>

      <section className="card-grid">
        {cards.map((card) => (
          <article key={card.title} className="card">
            <h2>{card.title}</h2>
            <p>{card.description}</p>
            <Link href={card.href} className="card-link">
              打开页面 →
            </Link>
          </article>
        ))}
      </section>
    </main>
  );
}
