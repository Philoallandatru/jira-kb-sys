"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { askJiraDocsQuestion, type JiraDocsQAResponse } from "@/lib/api";

export function JiraDocsQAClient() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [question, setQuestion] = useState("");
  const [snapshotDate, setSnapshotDate] = useState(today);
  const [topK, setTopK] = useState(5);
  const [result, setResult] = useState<JiraDocsQAResponse | null>(null);
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
      const nextResult = await askJiraDocsQuestion({
        question: question.trim(),
        snapshot_date: snapshotDate || undefined,
        top_k: topK,
      });
      setResult(nextResult);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "联合问答失败");
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
            <label htmlFor="jira-docs-qa-question">问题</label>
            <textarea
              id="jira-docs-qa-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="例如：哪个 Jira 最可能违反 nvme_admin_timeout 相关设计约束？"
            />
          </div>
          <div className="field">
            <label htmlFor="jira-docs-qa-date">Snapshot Date</label>
            <input
              id="jira-docs-qa-date"
              type="date"
              value={snapshotDate}
              onChange={(event) => setSnapshotDate(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="jira-docs-qa-topk">检索 Top K</label>
            <input
              id="jira-docs-qa-topk"
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            />
          </div>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "分析中..." : "执行 Jira + Docs QA"}
          </button>
        </form>
      </aside>

      <section className="panel">
        <h2>问答结果</h2>
        {error && <div className="empty-state">{error}</div>}
        {!error && !result && <div className="empty-state">提交问题后，这里会显示联合答案、文档证据和 Jira 上下文。</div>}
        {result && (
          <>
            <div className="status-line">
              snapshot: {result.snapshot_date} | mode: {result.mode} | jira items: {result.jira_context.length}
            </div>
            <div className="summary-section">
              <h3>Answer</h3>
              <p>{result.answer}</p>
            </div>
            <div className="summary-section">
              <h3>Relevant Jira Context</h3>
              <div className="settings-stack">
                {result.jira_context.map((item) => (
                  <article key={item.issue_key} className="citation-card">
                    <div className="citation-meta">
                      {item.issue_key} | {item.status} | {item.team ?? "UNKNOWN"} | {item.priority ?? "-"}
                    </div>
                    <div>{item.summary}</div>
                    <div className="citation-meta" style={{ marginTop: 8 }}>
                      {item.reason}
                    </div>
                  </article>
                ))}
              </div>
            </div>
            <div className="summary-section">
              <h3>Document Citations</h3>
              <div className="settings-stack">
                {result.doc_citations.map((citation, index) => (
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
