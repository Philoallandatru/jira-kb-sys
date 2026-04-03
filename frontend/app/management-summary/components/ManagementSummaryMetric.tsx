"use client";

import { MetricCard } from "@/components/summary/MetricCard";

export function ManagementSummaryMetric({ label, value }: { label: string; value: number }) {
  return <MetricCard label={label} value={value} />;
}
