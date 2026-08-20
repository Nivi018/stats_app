"use client";

import { useReportWebVitals } from "next/web-vitals";

type VitalsMetric = { name: string; value: number; rating: string };

// Registra Core Web Vitals como mediciones (objetivo demo, US3).
function logWebVitals(metric: VitalsMetric) {
  console.info(
    JSON.stringify({
      source: "web-vitals",
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
    }),
  );
}

export function WebVitals() {
  useReportWebVitals(logWebVitals);
  return null;
}
