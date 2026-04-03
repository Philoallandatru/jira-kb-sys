"use client";

import type { IssueItem } from "@/lib/api";

type IssueListProps = {
  items: IssueItem[];
  selectedIssue: string;
  loading: boolean;
  onSelect: (issueKey: string) => void;
};

export function IssueList({ items, selectedIssue, loading, onSelect }: IssueListProps) {
  if (loading) {
    return <div className="empty-state">正在加载 Issue 列表...</div>;
  }

  if (!items.length) {
    return <div className="empty-state">当前筛选条件下没有 Issue。</div>;
  }

  return (
    <div className="stack-list">
      {items.map((item) => (
        <button
          key={item.issue_key}
          className={`list-button ${selectedIssue === item.issue_key ? "active" : ""}`}
          onClick={() => onSelect(item.issue_key)}
          type="button"
        >
          <strong>{item.issue_key}</strong>
          <span>{item.status}</span>
          <span>{item.team || "未标注团队"}</span>
          <span>{item.summary}</span>
        </button>
      ))}
    </div>
  );
}
