/**
 * CALLING SPEC:
 * - Purpose: define dashboard analytics contracts for the frontend.
 * - Inputs: frontend modules that render dashboard charts, summaries, and reconciliation views.
 * - Outputs: dashboard and analytics interfaces.
 * - Side effects: type declarations only.
 */

import type { DashboardReconciliation } from "./accounts";

export interface DailyExpensePoint {
  date: string;
  currency_code: string;
  total_minor: number;
}

export interface TopTag {
  tag: string;
  currency_code: string;
  total_minor: number;
}

export interface DashboardKpis {
  expense_total_minor: number;
  income_total_minor: number;
  net_total_minor: number;
  average_expense_day_minor: number;
  median_expense_day_minor: number;
  spending_days: number;
  average_day_to_day_minor: number;
  median_day_to_day_minor: number;
}

export interface DashboardFilterGroupSummary {
  filter_group_id: string;
  key: string;
  name: string;
  color: string | null;
  total_minor: number;
  share: number;
  tag_totals: Record<string, number>;
}

export interface DashboardDailySpendingPoint {
  date: string;
  expense_total_minor: number;
  filter_group_totals: Record<string, number>;
}

export interface DashboardMonthlyTrendPoint {
  month: string;
  expense_total_minor: number;
  income_total_minor: number;
  filter_group_totals: Record<string, number>;
}

export interface DashboardBreakdownItem {
  label: string;
  total_minor: number;
  share: number;
}

export interface DashboardWeekdaySpendingPoint {
  weekday: string;
  total_minor: number;
}

export interface DashboardLargestExpenseItem {
  id: string;
  occurred_at: string;
  name: string;
  to_entity: string | null;
  amount_minor: number;
  matching_filter_group_keys: string[];
}

export interface DashboardProjection {
  is_current_month: boolean;
  days_elapsed: number;
  days_remaining: number;
  spent_to_date_minor: number;
  projected_total_minor: number | null;
  projected_remaining_minor: number | null;
  projected_filter_group_totals: Record<string, number>;
}

export interface DashboardTimeline {
  months: string[];
}

export interface Dashboard {
  month: string;
  currency_code: string;
  kpis: DashboardKpis;
  filter_groups: DashboardFilterGroupSummary[];
  daily_spending: DashboardDailySpendingPoint[];
  monthly_trend: DashboardMonthlyTrendPoint[];
  spending_by_from: DashboardBreakdownItem[];
  spending_by_to: DashboardBreakdownItem[];
  spending_by_tag: DashboardBreakdownItem[];
  weekday_spending: DashboardWeekdaySpendingPoint[];
  largest_expenses: DashboardLargestExpenseItem[];
  projection: DashboardProjection;
  reconciliation: DashboardReconciliation[];
}
