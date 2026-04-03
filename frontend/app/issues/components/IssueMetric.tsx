"use client";

import { MetricCard } from "@/components/summary/MetricCard";

export function IssueMetric({ label, value }: { label: string; value: string }) {
  return <MetricCard label={label} value={value} valueFontSize="1.1rem" />;
}
