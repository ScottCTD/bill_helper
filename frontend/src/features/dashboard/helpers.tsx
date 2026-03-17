/**
 * CALLING SPEC:
 * - Purpose: shared dashboard tabs, chart helpers, date utilities, and chart container rendering for the dashboard route.
 * - Inputs: typed dashboard read models plus React chart container children.
 * - Outputs: derived chart data, display helpers, and reusable dashboard UI utilities.
 * - Side effects: React rendering only inside `DashboardChartContainer`.
 */

import { useEffect, useRef, useState, type ReactElement } from "react";

import { formatMinor } from "../../lib/format";
import type { Dashboard } from "../../lib/types";

export type DashboardTab = "overview" | "daily" | "breakdowns" | "insights" | "agent";
export type DashboardViewMode = "month" | "year";

export const BUILTIN_FILTER_GROUP_ORDER = ["day_to_day", "fixed", "one_time", "transfers", "untagged"] as const;
export type BuiltinFilterGroupKey = (typeof BUILTIN_FILTER_GROUP_ORDER)[number];

/** Income filter groups (for income segmentation in trend chart). */
export const INCOME_FILTER_GROUP_KEYS = ["salary", "other_income"] as const;
export type IncomeFilterGroupKey = (typeof INCOME_FILTER_GROUP_KEYS)[number];

export function isIncomeFilterGroupKey(key: string): boolean {
  return (INCOME_FILTER_GROUP_KEYS as readonly string[]).includes(key);
}

/** Expense stacked bar order from bottom to top. */
export const INCOME_TREND_SEGMENT_ORDER = ["fixed", "transfers", "one_time", "day_to_day", "untagged"] as const;
/** Income stacked bar order from bottom to top. */
export const INCOME_BAR_SEGMENT_ORDER = ["salary", "other_income"] as const;

export function sortByBuiltinOrder<T extends { key: string }>(groups: T[]): T[] {
  return [...groups].sort((a, b) => {
    const ai = BUILTIN_FILTER_GROUP_ORDER.indexOf(a.key as BuiltinFilterGroupKey);
    const bi = BUILTIN_FILTER_GROUP_ORDER.indexOf(b.key as BuiltinFilterGroupKey);
    if (ai === -1 && bi === -1) return a.key.localeCompare(b.key);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
}

export function builtinGroupColor(key: string): string {
  const index = BUILTIN_FILTER_GROUP_ORDER.indexOf(key as BuiltinFilterGroupKey);
  return dashboardBarColor(index >= 0 ? index : BUILTIN_FILTER_GROUP_ORDER.length);
}

export function builtinIncomeGroupColor(key: string): string {
  const index = INCOME_BAR_SEGMENT_ORDER.indexOf(key as IncomeFilterGroupKey);
  if (index >= 0) return ["#047857", "#059669"][index] ?? CHART_COLORS.income;
  return CHART_COLORS.income;
}

/** Income bar segment order from bottom to top: salary, then other_income. */
export function sortByIncomeBarOrder<T extends { key: string }>(groups: T[]): T[] {
  return [...groups].sort((a, b) => {
    const ai = INCOME_BAR_SEGMENT_ORDER.indexOf(a.key as IncomeFilterGroupKey);
    const bi = INCOME_BAR_SEGMENT_ORDER.indexOf(b.key as IncomeFilterGroupKey);
    if (ai === -1 && bi === -1) return a.key.localeCompare(b.key);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
}

export function sortByIncomeTrendOrder<T extends { key: string }>(groups: T[]): T[] {
  return [...groups].sort((a, b) => {
    const ai = INCOME_TREND_SEGMENT_ORDER.indexOf(a.key as (typeof INCOME_TREND_SEGMENT_ORDER)[number]);
    const bi = INCOME_TREND_SEGMENT_ORDER.indexOf(b.key as (typeof INCOME_TREND_SEGMENT_ORDER)[number]);
    if (ai === -1 && bi === -1) return a.key.localeCompare(b.key);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
}

export const DASHBOARD_TABS: Array<{ id: DashboardTab; label: string; description: string }> = [
  { id: "overview", label: "Overview", description: "Month snapshot, projection, and filter-group mix" },
  { id: "daily", label: "Spending", description: "Daily spending and month-over-month filter-group comparisons" },
  { id: "breakdowns", label: "Breakdowns", description: "From / to / tag analysis" },
  { id: "insights", label: "Insights", description: "Weekdays, yearly views, outliers, and reconciliation" },
  { id: "agent", label: "Agent", description: "Usage cost, token mix, surface comparison, and expensive runs" }
];

export const CHART_COLORS = {
  income: "rgb(var(--chart-income))",
  expense: "rgb(var(--chart-expense))",
  net: "rgb(var(--chart-net))",
  muted: "hsl(var(--muted-foreground))",
  destination: "rgb(var(--chart-destination))",
  source: "rgb(var(--chart-source))"
};

const DASHBOARD_BAR_COLORS = [
  "rgb(var(--chart-segment-1))",
  "rgb(var(--chart-segment-2))",
  "rgb(var(--chart-segment-3))",
  "rgb(var(--chart-segment-4))",
  "rgb(var(--chart-segment-5))",
  "rgb(var(--chart-segment-6))",
  "rgb(var(--chart-segment-7))",
  "rgb(var(--chart-segment-8))"
];

const DASHBOARD_PIE_COLORS = [
  "rgb(var(--chart-pie-1))",
  "rgb(var(--chart-pie-2))",
  "rgb(var(--chart-pie-3))",
  "rgb(var(--chart-pie-4))",
  "rgb(var(--chart-pie-5))",
  "rgb(var(--chart-pie-6))",
  "rgb(var(--chart-pie-7))",
  "rgb(var(--chart-pie-8))"
];

export const DASHBOARD_PIE_ANIMATION_PROPS = {
  animationBegin: 0,
  animationDuration: 420,
  animationEasing: "ease-out" as const
};

export const TIMELINE_WHEEL_LOCK_MS = 180;

export function axisTick(value: number | string) {
  const numericValue = typeof value === "number" ? value : Number(value);
  return `${Math.round((Number.isFinite(numericValue) ? numericValue : 0) / 100).toLocaleString()}`;
}

export function toMinorValue(value: unknown): number {
  if (Array.isArray(value) && value.length > 0) {
    return toMinorValue(value[0]);
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return 0;
}

export function tooltipAmount(currencyCode: string, value: unknown): string {
  return formatMinor(toMinorValue(value), currencyCode);
}

export function tooltipAmountWithName(
  currencyCode: string,
  value: unknown,
  name: string | number | undefined
): [string, string] {
  return [tooltipAmount(currencyCode, value), String(name ?? "")];
}

export function dashboardBarColor(index: number): string {
  return DASHBOARD_BAR_COLORS[index % DASHBOARD_BAR_COLORS.length];
}

export function dashboardPieColor(index: number): string {
  return DASHBOARD_PIE_COLORS[index % DASHBOARD_PIE_COLORS.length];
}

export function monthDate(monthKey: string): Date {
  const [year, month] = monthKey.split("-").map(Number);
  return new Date(year, month - 1, 1);
}

export function shiftMonthKey(monthKey: string, monthDelta: number): string {
  const [year, month] = monthKey.split("-").map(Number);
  const shifted = new Date(year, month - 1 + monthDelta, 1);
  return `${shifted.getFullYear()}-${`${shifted.getMonth() + 1}`.padStart(2, "0")}`;
}

export function buildYearMonthKeys(year: number): string[] {
  return Array.from({ length: 12 }, (_, index) => `${year}-${`${index + 1}`.padStart(2, "0")}`);
}

export function buildTimelineYears(monthKeys: string[]): string[] {
  return Array.from(new Set(monthKeys.map((monthKey) => monthKey.slice(0, 4))));
}

export function pickTimelineMonthForYear(monthKeys: string[], yearKey: string, preferredMonthKey: string): string | null {
  const yearMonths = monthKeys.filter((monthKey) => monthKey.startsWith(`${yearKey}-`));
  if (yearMonths.length === 0) {
    return null;
  }
  const preferredMonthNumber = Number(preferredMonthKey.slice(5, 7));
  return (
    yearMonths.find((monthKey) => Number(monthKey.slice(5, 7)) === preferredMonthNumber) ??
    yearMonths[yearMonths.length - 1]
  );
}

export function formatMonthShort(monthKey: string): string {
  return monthDate(monthKey).toLocaleDateString(undefined, { month: "short" });
}

export function formatMonthLong(monthKey: string): string {
  return monthDate(monthKey).toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

/** Extract day-only label from YYYY-MM-DD for daily chart x-axis. */
export function formatDayFromDate(dateStr: string): string {
  const parts = String(dateStr ?? "").split("-");
  const day = parts[2];
  return day ? String(parseInt(day, 10)) : "";
}

export function filterGroupTotalForMonth(dashboard: Dashboard | undefined, filterGroupKey: string): number {
  return dashboard?.filter_groups.find((group) => group.key === filterGroupKey)?.total_minor ?? 0;
}

/** Income filter group total from dashboard monthly_trend for a given month. */
function incomeFilterGroupTotalForMonth(
  dashboard: Dashboard | undefined,
  monthKey: string,
  groupKey: string
): number {
  const trendPoint = dashboard?.monthly_trend?.find((p) => p.month === monthKey);
  return trendPoint?.income_filter_group_totals?.[groupKey] ?? 0;
}

export function buildYearlyOverviewData(
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>,
  filterGroups: Dashboard["filter_groups"]
) {
  return monthKeys.map((monthKey) => {
    const monthDashboard = dashboardsByMonth.get(monthKey);
    const expenseTotals = Object.fromEntries(
      filterGroups
        .filter((g) => !INCOME_FILTER_GROUP_KEYS.includes(g.key as IncomeFilterGroupKey))
        .map((group) => [group.key, filterGroupTotalForMonth(monthDashboard, group.key)])
    );
    const incomeTotals = Object.fromEntries(
      INCOME_FILTER_GROUP_KEYS.map((key) => [
        key,
        incomeFilterGroupTotalForMonth(monthDashboard, monthKey, key)
      ])
    );
    return {
      month: formatMonthShort(monthKey),
      expense_total_minor: monthDashboard?.kpis.expense_total_minor ?? 0,
      income_total_minor: monthDashboard?.kpis.income_total_minor ?? 0,
      ...expenseTotals,
      ...incomeTotals
    };
  });
}

export function buildYearOverYearData(
  selectedYearMonths: string[],
  previousYearMonths: string[],
  dashboardsByMonth: Map<string, Dashboard>
) {
  return selectedYearMonths.map((monthKey, index) => {
    const previousMonthKey = previousYearMonths[index];
    const selectedDashboard = dashboardsByMonth.get(monthKey);
    const previousDashboard = dashboardsByMonth.get(previousMonthKey);
    return {
      month: formatMonthShort(monthKey),
      current_expense_total_minor: selectedDashboard?.kpis.expense_total_minor ?? 0,
      previous_expense_total_minor: previousDashboard?.kpis.expense_total_minor ?? 0,
      current_income_total_minor: selectedDashboard?.kpis.income_total_minor ?? 0,
      previous_income_total_minor: previousDashboard?.kpis.income_total_minor ?? 0
    };
  });
}

export function sumDashboardKpiForMonths(
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>,
  key: "expense_total_minor" | "income_total_minor" | "net_total_minor"
): number {
  return monthKeys.reduce((sum, monthKey) => sum + (dashboardsByMonth.get(monthKey)?.kpis[key] ?? 0), 0);
}

export function sumFilterGroupForMonths(
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>,
  filterGroupKey: string
): number {
  return monthKeys.reduce(
    (sum, monthKey) => sum + filterGroupTotalForMonth(dashboardsByMonth.get(monthKey), filterGroupKey),
    0
  );
}

export function buildYearFilterGroupTotals(
  filterGroups: Dashboard["filter_groups"],
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>
) {
  return filterGroups.map((group) => ({
    ...group,
    total_minor: sumFilterGroupForMonths(monthKeys, dashboardsByMonth, group.key)
  }));
}

export function buildYearLargestExpenses(
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>,
  limit = 8
): Dashboard["largest_expenses"] {
  return monthKeys
    .flatMap((monthKey) => dashboardsByMonth.get(monthKey)?.largest_expenses ?? [])
    .sort((left, right) => {
      if (right.amount_minor !== left.amount_minor) {
        return right.amount_minor - left.amount_minor;
      }
      if (right.occurred_at !== left.occurred_at) {
        return right.occurred_at.localeCompare(left.occurred_at);
      }
      return right.name.localeCompare(left.name);
    })
    .slice(0, limit);
}

export function median(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return Math.round((sorted[middle - 1] + sorted[middle]) / 2);
  }
  return sorted[middle];
}

export function formatDelta(deltaMinor: number, currencyCode: string): string {
  const prefix = deltaMinor > 0 ? "+" : deltaMinor < 0 ? "-" : "";
  return `${prefix}${formatMinor(Math.abs(deltaMinor), currencyCode)}`;
}

type ChartDimensions = {
  width: number;
  height: number;
};

export function DashboardChartContainer({
  children
}: {
  children: (dimensions: ChartDimensions) => ReactElement;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState<ChartDimensions | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }

    const updateDimensions = () => {
      const nextWidth = Math.floor(element.clientWidth);
      const nextHeight = Math.floor(element.clientHeight);
      if (nextWidth <= 0 || nextHeight <= 0) {
        return;
      }

      setDimensions((current) => {
        if (current?.width === nextWidth && current?.height === nextHeight) {
          return current;
        }
        return { width: nextWidth, height: nextHeight };
      });
    };

    updateDimensions();
    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => {
      updateDimensions();
    });
    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, []);

  return <div ref={containerRef} className="h-full min-w-0">{dimensions ? children(dimensions) : null}</div>;
}

export function buildDailyChartData(data: Dashboard) {
  return data.daily_spending.map((point) => ({
    date: point.date,
    expense_total_minor: point.expense_total_minor,
    ...point.filter_group_totals
  }));
}

export function buildMonthlyChartData(data: Dashboard) {
  return data.monthly_trend.map((point) => ({
    month: point.month,
    expense_total_minor: point.expense_total_minor,
    income_total_minor: point.income_total_minor,
    ...point.filter_group_totals,
    ...(point.income_filter_group_totals ?? {})
  }));
}

const MAX_TREND_MONTHS = 12;

/** Limit trend chart data to months with income/expense activity, at most MAX_TREND_MONTHS. */
export function limitTrendDataToMonthsWithData<T extends { income_total_minor?: unknown; expense_total_minor?: unknown }>(
  points: T[],
  maxMonths = MAX_TREND_MONTHS
): T[] {
  const withData = points.filter(
    (p) => Number(p.income_total_minor ?? 0) > 0 || Number(p.expense_total_minor ?? 0) > 0
  );
  return withData.slice(-maxMonths);
}

export function filterGroupNamesByKey(data: Dashboard) {
  return new Map(data.filter_groups.map((group) => [group.key, group.name]));
}

/** Aggregate tag_totals across all year months for a single filter group key. */
export function buildYearFilterGroupTagTotals(
  filterGroupKey: string,
  selectedYearMonths: string[],
  yearlyDashboardsByMonth: Map<string, Dashboard>
): Record<string, number> {
  const totals: Record<string, number> = {};
  for (const monthKey of selectedYearMonths) {
    const group = yearlyDashboardsByMonth.get(monthKey)?.filter_groups.find((g) => g.key === filterGroupKey);
    if (!group) continue;
    for (const [tag, amount] of Object.entries(group.tag_totals)) {
      totals[tag] = (totals[tag] ?? 0) + amount;
    }
  }
  return totals;
}

/** Build per-group tag_totals for the yearly Sankey (aggregated across all year months). */
export function buildYearlyFilterGroupsWithTagTotals(
  filterGroups: Dashboard["filter_groups"],
  selectedYearMonths: string[],
  yearlyDashboardsByMonth: Map<string, Dashboard>
): Dashboard["filter_groups"] {
  return filterGroups.map((group) => ({
    ...group,
    tag_totals: buildYearFilterGroupTagTotals(group.key, selectedYearMonths, yearlyDashboardsByMonth)
  }));
}
