"use client";

export function MetricCard({
  label,
  value,
  valueFontSize,
}: {
  label: string;
  value: string | number;
  valueFontSize?: string;
}) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={valueFontSize ? { fontSize: valueFontSize } : undefined}>
        {value}
      </div>
    </div>
  );
}
