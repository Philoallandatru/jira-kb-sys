"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { askDocsQuestion, type DocsQAResponse } from "@/lib/api";

export function DocsQAClient() {
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(5);
  const [result, setResult] = useState<DocsQAResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) {
      setError("请输入问题。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const nextResult = await askDocsQuestion({
        question: question.trim(),
        top_k: topK,
      });
      setResult(nextResult);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "文档问答失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="qa-layout">
      <aside className="panel">
        <h2>提问参数</h2>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="docs-qa-question">问题</label>
            <textarea
              id="docs-qa-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="例如：namespace recovery 的前置条件是什么？"
            />
          </div>
          <div className="field">
            <label htmlFor="docs-qa-topk">检索 Top K</label>
            <input
              id="docs-qa-topk"
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            />
          </div>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "检索中..." : "执行 Docs QA"}
          </button>
        </form>
      </aside>

      <section className="panel">
        <h2>问答结果</h2>
        {error && <div className="empty-state">{error}</div>}
        {!error && !result && <div className="empty-state">提交问题后，这里会显示答案、模式和证据引用。</div>}
        {result && (
          <>
            <div className="status-line">
              mode: {result.mode} | citations: {result.citations.length}
            </div>
            <div className="summary-section">
              <h3>Answer</h3>
              <p>{result.answer}</p>
            </div>
            <div className="summary-section">
              <h3>Citations</h3>
              <div className="settings-stack">
                {result.citations.map((citation, index) => (
                  <article key={`${citation.source_path}-${index}`} className="citation-card">
                    <div className="citation-meta">
                      {citation.source_path}
                      {citation.section_path.length ? ` | ${citation.section_path.join(" / ")}` : ""}
                    </div>
                    <div>{citation.quote}</div>
                  </article>
                ))}
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
