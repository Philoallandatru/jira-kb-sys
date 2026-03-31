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
    description: "查看 Jira 列表、单 Jira 详情、spec/policy 关联和深度分析。",
    href: "/issues",
  },
  {
    title: "Prompt Settings",
    description: "维护默认语言、输出长度和各场景 custom prompt。",
    href: "/settings",
  },
];

export default function HomePage() {
  return (
    <main>
      <section className="hero">
        <h1>Retro Modern Control Surface</h1>
        <p>
          这个独立前端已经接入 Dashboard、日报、管理层摘要、Issue Detail 与 Prompt Settings。
          当前仍在继续补充知识库问答、任务中心和更完整的 Jira 增量事件流。
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
