import { JiraDocsQAClient } from "./JiraDocsQAClient";

export default function JiraDocsQAPage() {
  return (
    <main>
      <section className="hero">
        <h1>Jira + Docs QA</h1>
        <p>把 Jira 快照上下文与本地文档证据组合起来，做联合问答并展示相关 Jira 与引用片段。</p>
      </section>
      <JiraDocsQAClient />
    </main>
  );
}
