"use client";

import { useEffect, useState } from "react";
import { getDailyReport, listDailyReports, type DailyReportDetail, type DailyReportListItem } from "@/lib/api";
import { ReportDetailPanel } from "./components/ReportDetailPanel";
import { ReportsHistoryList } from "./components/ReportsHistoryList";

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
        <ReportsHistoryList items={items} selectedDate={selectedDate} loading={loadingList} onSelectDate={setSelectedDate} />
      </aside>

      <section className="panel">
        <h2>日报详情</h2>
        {error && <div className="empty-state">{error}</div>}
        {loadingDetail && <div className="empty-state">正在加载日报详情。</div>}
        {!loadingDetail && detail && <ReportDetailPanel detail={detail} />}
      </section>
    </div>
  );
}
