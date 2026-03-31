import { DocsQAClient } from "./DocsQAClient";

export default function DocsQAPage() {
  return (
    <main>
      <section className="hero">
        <h1>Docs QA</h1>
        <p>对本地 spec、policy 和 markdown chunks 发起问答，返回答案、证据引用和检索模式信息。</p>
      </section>
      <DocsQAClient />
    </main>
  );
}
