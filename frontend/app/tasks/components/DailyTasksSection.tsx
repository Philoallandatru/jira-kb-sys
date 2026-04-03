"use client";

type DailyTasksSectionProps = {
  reportDate: string;
  onReportDateChange: (value: string) => void;
  onAnalyze: () => void;
  onExportReport: () => void;
};

export function DailyTasksSection({ reportDate, onReportDateChange, onAnalyze, onExportReport }: DailyTasksSectionProps) {
  return (
    <div className="summary-section">
      <h3>日报任务</h3>
      <div className="field">
        <label htmlFor="task-report-date">报告日期</label>
        <input id="task-report-date" type="date" value={reportDate} onChange={(event) => onReportDateChange(event.target.value)} />
      </div>
      <div className="settings-stack">
        <button className="secondary-button" type="button" onClick={onAnalyze}>
          生成日报分析
        </button>
        <button className="secondary-button" type="button" onClick={onExportReport}>
          导出日报
        </button>
      </div>
    </div>
  );
}
