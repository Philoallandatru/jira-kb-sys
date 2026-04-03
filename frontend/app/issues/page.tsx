import { IssuesClient } from "./IssuesClient";

export default function IssuesPage() {
  return (
    <main>
      <section className="hero">
        <h1>Issues</h1>
        <p>查看 Jira 列表、基础分析和单 Jira 深度分析，拆出 spec、policy、评论洞察和相关设计依据。</p>
      </section>
      <IssuesClient />
    </main>
  );
}
