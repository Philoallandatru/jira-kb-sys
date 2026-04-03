"use client";

export function SummaryListSection({ title, items, emptyText = "无" }: { title: string; items: string[]; emptyText?: string }) {
  return (
    <div className="summary-section">
      <h3>{title}</h3>
      <ul className="summary-list">
        {(items.length ? items : [emptyText]).map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
