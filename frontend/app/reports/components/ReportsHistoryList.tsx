"use client";

import type { DailyReportListItem } from "@/lib/api";

type ReportsHistoryListProps = {
  items: DailyReportListItem[];
  selectedDate: string;
  loading: boolean;
  onSelectDate: (value: string) => void;
};

export function ReportsHistoryList({ items, selectedDate, loading, onSelectDate }: ReportsHistoryListProps) {
  return (
    <>
      <h2>历史日期</h2>
      {loading && <div className="empty-state">正在加载日报列表。</div>}
      {!loading && (
        <div className="stack-list">
          {items.map((item) => (
            <button
              key={item.report_date}
              className={`list-button ${selectedDate === item.report_date ? "active" : ""}`}
              onClick={() => onSelectDate(item.report_date)}
              type="button"
            >
              <strong>{item.report_date}</strong>
              <span>{item.overall_health ?? "未分析"}</span>
              <span>issues {item.issue_count}</span>
              <span>blocked {item.blocked_count}</span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}
