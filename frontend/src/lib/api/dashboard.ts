/**
 * CALLING SPEC:
 * - Purpose: expose dashboard API calls for the frontend.
 * - Inputs: month scope selectors for dashboard reads.
 * - Outputs: dashboard read models and timeline metadata.
 * - Side effects: HTTP requests only.
 */

import type { Dashboard, DashboardTimeline } from "../types";
import { request } from "./core";

export function getDashboard(month: string): Promise<Dashboard> {
  return request<Dashboard>(`/api/v1/dashboard?month=${month}`);
}

export function getDashboardTimeline(): Promise<DashboardTimeline> {
  return request<DashboardTimeline>("/api/v1/dashboard/timeline");
}
