"use client";

import { useEffect, useState } from "react";
import { getDailyReport, listDailyReports, type DailyReportDetail, type DailyReportListItem } from "@/lib/api";

export function ReportsClient() {
  const [items, setItems] = useState<DailyReportListItem[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [detail, setDetail] = useState<DailyReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listDailyReports()
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        if (result.items[0]) {
          setSelectedDate(result.items[0].report_date);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "日报列表加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingList(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedDate) return;
    let cancelled = false;
    setLoadingDetail(true);
    getDailyReport(selectedDate)
      .then((result) => {
        if (!cancelled) {
          setDetail(result);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "日报详情加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingDetail(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDate]);

  return (
    <div className="management-layout">
      <aside className="panel">
        <h2>历史日期</h2>
        {loadingList && <div className="empty-state">正在加载日报列表。</div>}
        {!loadingList && (
          <div className="stack-list">
            {items.map((item) => (
              <button
                key={item.report_date}
                className={`list-button ${selectedDate === item.report_date ? "active" : ""}`}
                onClick={() => setSelectedDate(item.report_date)}
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
      </aside>

      <section className="panel">
        <h2>日报详情</h2>
        {error && <div className="empty-state">{error}</div>}
        {loadingDetail && <div className="empty-state">正在加载日报详情。</div>}
        {!loadingDetail && detail && (
          <>
            <div className="status-line">报告日期 · {detail.report.report_date}</div>
            <div className="summary-section" style={{ marginTop: 16 }}>
              <div className="metric-grid">
                <Metric label="总 Jira" value={detail.report.metrics.total_issues} />
                <Metric label="新增" value={detail.report.metrics.new_issues} />
                <Metric label="关闭" value={detail.report.metrics.closed_issues} />
                <Metric label="阻塞" value={detail.report.metrics.blocked_issues} />
                <Metric label="陈旧" value={detail.report.metrics.stale_issues} />
              </div>
            </div>

            {detail.daily_analysis && (
              <>
                <SummarySection title="总体健康度" items={[detail.daily_analysis.overall_health]} />
                <SummarySection title="重点风险" items={detail.daily_analysis.top_risks} />
                <SummarySection title="建议动作" items={detail.daily_analysis.recommended_actions} />
              </>
            )}

            <SummarySection
              title="优先级 Jira"
              items={detail.report.priority_issues.map(
                (item) =>
                  `${item.issue_key} | ${item.status} | ${item.priority ?? "-"} | ${item.summary} | ${item.change_summary}`
              )}
            />

            <SummarySection
              title="单 Jira 分析摘录"
              items={detail.issue_analyses.map(
                (item) => `${item.issue_key} | ${item.confidence} | ${item.suspected_root_cause}`
              )}
            />
          </>
        )}
      </section>
    </div>
  );
}

function SummarySection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="summary-section">
      <h3>{title}</h3>
      <ul className="summary-list">
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}
