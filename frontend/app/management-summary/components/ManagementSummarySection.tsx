"use client";

import { SummaryListSection } from "@/components/summary/SummaryListSection";

export function ManagementSummarySection({ title, items }: { title: string; items: string[] }) {
  return <SummaryListSection title={title} items={items} />;
}
