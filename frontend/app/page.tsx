import Link from "next/link";

const cards = [
  {
    title: "Task Center",
    description:
      "Launch sync, build-docs, analyze, report, and management-summary background tasks from one place.",
    href: "/tasks",
  },
  {
    title: "Management Summary",
    description:
      "A management-facing summary focused on recent Jira movement, risks, trends, collaboration quality, and follow-through.",
    href: "/management-summary",
  },
  {
    title: "Dashboard",
    description: "Review daily metrics, team filters, status breakdowns, and the highest-risk Jira changes.",
    href: "/dashboard",
  },
  {
    title: "Daily Reports",
    description: "Browse generated daily reports, historical snapshots, and AI-authored daily conclusions.",
    href: "/reports",
  },
  {
    title: "Issues",
    description: "Inspect Jira lists, issue details, spec and policy relations, and deep analysis for a single issue.",
    href: "/issues",
  },
  {
    title: "Docs QA",
    description: "Ask questions against local specs, policies, and markdown chunks with traceable citations.",
    href: "/docs-qa",
  },
  {
    title: "Jira + Docs QA",
    description: "Combine Jira snapshot context, issue analyses, and document evidence in a single QA flow.",
    href: "/jira-docs-qa",
  },
  {
    title: "Prompt Settings",
    description: "Maintain default language, output length, and scenario-specific custom prompts.",
    href: "/settings",
  },
];

export default function HomePage() {
  return (
    <main>
      <section className="hero">
        <h1>Retro Modern Control Surface</h1>
        <p>
          This frontend now exposes the task center, dashboard, daily reports, issue detail and deep analysis,
          docs QA, Jira plus docs QA, management summary, and prompt settings. The remaining gaps are focused on
          operational depth rather than missing surfaces.
        </p>
      </section>

      <section className="card-grid">
        {cards.map((card) => (
          <article key={card.title} className="card">
            <h2>{card.title}</h2>
            <p>{card.description}</p>
            <Link href={card.href} className="card-link">
              Open page
            </Link>
          </article>
        ))}
      </section>
    </main>
  );
}
