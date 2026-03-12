import { useEffect, useRef, useState, type KeyboardEvent, type ReactElement, type WheelEvent } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { PageHeader } from "../components/layout/PageHeader";
import { StatBlock } from "../components/layout/StatBlock";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { WorkspaceToolbar } from "../components/layout/WorkspaceToolbar";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { getDashboard, getDashboardTimeline } from "../lib/api";
import { currentMonth, formatMinor } from "../lib/format";
import { queryKeys } from "../lib/queryKeys";
import type { Dashboard } from "../lib/types";
import { cn } from "../lib/utils";

type DashboardTab = "overview" | "daily" | "breakdowns" | "insights";
type DashboardViewMode = "month" | "year";

const DASHBOARD_TABS: Array<{ id: DashboardTab; label: string; description: string }> = [
  { id: "overview", label: "Overview", description: "Month snapshot, projection, and filter-group mix" },
  { id: "daily", label: "Spending", description: "Daily spending and month-over-month filter-group comparisons" },
  { id: "breakdowns", label: "Breakdowns", description: "From / to / tag analysis" },
  { id: "insights", label: "Insights", description: "Weekdays, yearly views, outliers, and reconciliation" }
];

const CHART_COLORS = {
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
  "rgb(var(--chart-segment-6))"
];

const DASHBOARD_PIE_COLORS = [
  "rgb(var(--chart-pie-1))",
  "rgb(var(--chart-pie-2))",
  "rgb(var(--chart-pie-3))",
  "rgb(var(--chart-pie-4))",
  "rgb(var(--chart-pie-5))",
  "rgb(var(--chart-pie-6))"
];

const DASHBOARD_PIE_ANIMATION_PROPS = {
  animationBegin: 0,
  animationDuration: 420,
  animationEasing: "ease-out" as const
};

const TIMELINE_WHEEL_LOCK_MS = 180;

function axisTick(value: number | string) {
  const numericValue = typeof value === "number" ? value : Number(value);
  return `${Math.round((Number.isFinite(numericValue) ? numericValue : 0) / 100).toLocaleString()}`;
}

function toMinorValue(value: unknown): number {
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

function tooltipAmount(currencyCode: string, value: unknown): string {
  return formatMinor(toMinorValue(value), currencyCode);
}

function tooltipAmountWithName(currencyCode: string, value: unknown, name: string | number | undefined): [string, string] {
  return [tooltipAmount(currencyCode, value), String(name ?? "")];
}

function dashboardBarColor(index: number): string {
  return DASHBOARD_BAR_COLORS[index % DASHBOARD_BAR_COLORS.length];
}

function dashboardPieColor(index: number): string {
  return DASHBOARD_PIE_COLORS[index % DASHBOARD_PIE_COLORS.length];
}

function monthDate(monthKey: string): Date {
  const [year, month] = monthKey.split("-").map(Number);
  return new Date(year, month - 1, 1);
}

function shiftMonthKey(monthKey: string, monthDelta: number): string {
  const [year, month] = monthKey.split("-").map(Number);
  const shifted = new Date(year, month - 1 + monthDelta, 1);
  return `${shifted.getFullYear()}-${`${shifted.getMonth() + 1}`.padStart(2, "0")}`;
}

function buildYearMonthKeys(year: number): string[] {
  return Array.from({ length: 12 }, (_, index) => `${year}-${`${index + 1}`.padStart(2, "0")}`);
}

function buildTimelineYears(monthKeys: string[]): string[] {
  return Array.from(new Set(monthKeys.map((monthKey) => monthKey.slice(0, 4))));
}

function pickTimelineMonthForYear(monthKeys: string[], yearKey: string, preferredMonthKey: string): string | null {
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

function formatMonthShort(monthKey: string): string {
  return monthDate(monthKey).toLocaleDateString(undefined, { month: "short" });
}

function formatMonthLong(monthKey: string): string {
  return monthDate(monthKey).toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function filterGroupTotalForMonth(dashboard: Dashboard | undefined, filterGroupKey: string): number {
  return dashboard?.filter_groups.find((group) => group.key === filterGroupKey)?.total_minor ?? 0;
}

function buildYearlyOverviewData(
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>,
  filterGroups: Dashboard["filter_groups"]
) {
  return monthKeys.map((monthKey) => {
    const monthDashboard = dashboardsByMonth.get(monthKey);
    return {
      month: formatMonthShort(monthKey),
      expense_total_minor: monthDashboard?.kpis.expense_total_minor ?? 0,
      income_total_minor: monthDashboard?.kpis.income_total_minor ?? 0,
      ...Object.fromEntries(
        filterGroups.map((group) => [group.key, filterGroupTotalForMonth(monthDashboard, group.key)])
      )
    };
  });
}

function buildYearOverYearData(
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

function sumDashboardKpiForMonths(
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>,
  key: "expense_total_minor" | "income_total_minor" | "net_total_minor"
): number {
  return monthKeys.reduce((sum, monthKey) => sum + (dashboardsByMonth.get(monthKey)?.kpis[key] ?? 0), 0);
}

function sumFilterGroupForMonths(
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>,
  filterGroupKey: string
): number {
  return monthKeys.reduce(
    (sum, monthKey) => sum + filterGroupTotalForMonth(dashboardsByMonth.get(monthKey), filterGroupKey),
    0
  );
}

function buildYearFilterGroupTotals(
  filterGroups: Dashboard["filter_groups"],
  monthKeys: string[],
  dashboardsByMonth: Map<string, Dashboard>
) {
  return filterGroups.map((group) => ({
    ...group,
    total_minor: sumFilterGroupForMonths(monthKeys, dashboardsByMonth, group.key)
  }));
}

function buildYearLargestExpenses(
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

function median(values: number[]): number {
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

function formatDelta(deltaMinor: number, currencyCode: string): string {
  const prefix = deltaMinor > 0 ? "+" : deltaMinor < 0 ? "-" : "";
  return `${prefix}${formatMinor(Math.abs(deltaMinor), currencyCode)}`;
}

type ChartDimensions = {
  width: number;
  height: number;
};

function DashboardChartContainer({ children }: { children: (dimensions: ChartDimensions) => ReactElement }) {
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

  return (
    <div ref={containerRef} className="h-full min-w-0">
      {dimensions ? children(dimensions) : null}
    </div>
  );
}

function buildDailyChartData(data: Dashboard) {
  return data.daily_spending.map((point) => ({
    date: point.date,
    expense_total_minor: point.expense_total_minor,
    ...point.filter_group_totals
  }));
}

function buildMonthlyChartData(data: Dashboard) {
  return data.monthly_trend.map((point) => ({
    month: point.month,
    expense_total_minor: point.expense_total_minor,
    income_total_minor: point.income_total_minor,
    ...point.filter_group_totals
  }));
}

function filterGroupNamesByKey(data: Dashboard) {
  return new Map(data.filter_groups.map((group) => [group.key, group.name]));
}

export function DashboardPage() {
  const [month, setMonth] = useState(currentMonth());
  const [viewMode, setViewMode] = useState<DashboardViewMode>("month");
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const timelineItemRefs = useRef(new Map<string, HTMLButtonElement>());
  const timelineScrollRef = useRef<HTMLDivElement>(null);
  const timelineWheelLockRef = useRef<number | null>(null);
  const timelineScrollBehaviorRef = useRef<ScrollBehavior>("auto");
  const timelineQuery = useQuery({
    queryKey: queryKeys.dashboard.timeline,
    queryFn: getDashboardTimeline,
    staleTime: 60_000
  });
  const timelineMonths = timelineQuery.data?.months ?? [];
  const timelineYears = buildTimelineYears(timelineMonths);
  const selectedYear = Number(month.slice(0, 4));
  const selectedYearMonths = buildYearMonthKeys(selectedYear);
  const previousYearMonths = buildYearMonthKeys(selectedYear - 1);
  const yearlyMonthKeys = [...previousYearMonths, ...selectedYearMonths];

  const dashboardQuery = useQuery({
    queryKey: queryKeys.dashboard.month(month),
    queryFn: () => getDashboard(month)
  });
  const yearlyQueries = useQueries({
    queries: yearlyMonthKeys.map((monthKey) => ({
      queryKey: queryKeys.dashboard.month(monthKey),
      queryFn: () => getDashboard(monthKey),
      staleTime: 60_000
    }))
  });
  const timelineSelectionKey = viewMode === "month" ? month : String(selectedYear);
  const monthTimelineIndex = timelineMonths.indexOf(month);
  const yearTimelineIndex = timelineYears.indexOf(String(selectedYear));

  function setTimelineMonth(nextMonth: string, behavior: ScrollBehavior = "smooth") {
    if (!nextMonth || nextMonth === month) {
      return;
    }
    timelineScrollBehaviorRef.current = behavior;
    setMonth(nextMonth);
  }

  function centerTimelineItem(selectedItem: HTMLButtonElement, behavior: ScrollBehavior = "auto") {
    const timelineScroller = timelineScrollRef.current;
    if (!timelineScroller) {
      return;
    }

    const verticalScrollable = timelineScroller.scrollHeight > timelineScroller.clientHeight;
    const scrollerRect = timelineScroller.getBoundingClientRect();
    const itemRect = selectedItem.getBoundingClientRect();

    if (verticalScrollable) {
      const delta = itemRect.top + itemRect.height / 2 - (scrollerRect.top + scrollerRect.height / 2);
      const nextTop = timelineScroller.scrollTop + delta;
      timelineScroller.scrollTo({ top: nextTop, behavior });
      return;
    }

    const delta = itemRect.left + itemRect.width / 2 - (scrollerRect.left + scrollerRect.width / 2);
    const nextLeft = timelineScroller.scrollLeft + delta;
    timelineScroller.scrollTo({ left: nextLeft, behavior });
  }

  function registerTimelineItem(key: string, node: HTMLButtonElement | null) {
    if (!node) {
      timelineItemRefs.current.delete(key);
      return;
    }

    timelineItemRefs.current.set(key, node);
  }

  function handleTimelineWheel(event: WheelEvent<HTMLDivElement>) {
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX) || Math.abs(event.deltaY) < 4) {
      return;
    }
    event.preventDefault();
    if (timelineWheelLockRef.current !== null) {
      return;
    }
    shiftSelection(event.deltaY > 0 ? 1 : -1);
    if (typeof window !== "undefined") {
      timelineWheelLockRef.current = window.setTimeout(() => {
        timelineWheelLockRef.current = null;
      }, TIMELINE_WHEEL_LOCK_MS);
    }
  }

  function handleTimelineKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      shiftSelection(1);
      return;
    }
    if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      shiftSelection(-1);
    }
  }

  useEffect(() => {
    if (timelineMonths.length === 0 || monthTimelineIndex >= 0) {
      return;
    }
    const fallbackMonth = timelineMonths[timelineMonths.length - 1];
    if (fallbackMonth !== month) {
      setTimelineMonth(fallbackMonth, "auto");
    }
  }, [month, monthTimelineIndex, timelineMonths]);

  useEffect(() => {
    if (viewMode !== "year" || timelineYears.length === 0 || yearTimelineIndex >= 0) {
      return;
    }
    const fallbackYear = timelineYears[timelineYears.length - 1];
    const fallbackMonth = pickTimelineMonthForYear(timelineMonths, fallbackYear, month);
    if (fallbackMonth && fallbackMonth !== month) {
      setTimelineMonth(fallbackMonth, "auto");
    }
  }, [month, timelineMonths, timelineYears, viewMode, yearTimelineIndex]);

  useEffect(() => {
    const selectedItem = timelineItemRefs.current.get(timelineSelectionKey);
    if (!selectedItem) {
      return;
    }

    const behavior = timelineScrollBehaviorRef.current;
    timelineScrollBehaviorRef.current = "auto";

    const firstFrame = requestAnimationFrame(() => {
      centerTimelineItem(selectedItem, behavior);
    });

    return () => {
      cancelAnimationFrame(firstFrame);
    };
  }, [timelineSelectionKey, viewMode]);

  useEffect(
    () => () => {
      if (typeof window !== "undefined" && timelineWheelLockRef.current !== null) {
        window.clearTimeout(timelineWheelLockRef.current);
      }
    },
    []
  );

  if (timelineQuery.isLoading || dashboardQuery.isLoading) {
    return <p>Loading dashboard...</p>;
  }

  if (timelineQuery.isError) {
    return <p>Failed to load dashboard timeline: {(timelineQuery.error as Error).message}</p>;
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return <p>Failed to load dashboard: {(dashboardQuery.error as Error).message}</p>;
  }

  const data = dashboardQuery.data;
  const yearlyDashboardsByMonth = new Map<string, Dashboard>();
  yearlyQueries.forEach((query, index) => {
    if (query.data) {
      yearlyDashboardsByMonth.set(yearlyMonthKeys[index], query.data);
    }
  });
  const yearlyQueryError = yearlyQueries.find((query) => query.isError)?.error as Error | undefined;
  const yearlyQueriesLoading = yearlyQueries.some((query) => query.isLoading);
  const chartGroups = data.filter_groups.filter((group) => group.total_minor > 0);
  const displayGroups = chartGroups.length > 0 ? chartGroups : data.filter_groups;
  const dailyChartData = buildDailyChartData(data);
  const monthlyChartData = buildMonthlyChartData(data);
  const yearlyOverviewData = buildYearlyOverviewData(selectedYearMonths, yearlyDashboardsByMonth, data.filter_groups);
  const yearOverYearData = buildYearOverYearData(selectedYearMonths, previousYearMonths, yearlyDashboardsByMonth);
  const yearlyFilterGroupTotals = buildYearFilterGroupTotals(data.filter_groups, selectedYearMonths, yearlyDashboardsByMonth);
  const yearlyDisplayGroups = yearlyFilterGroupTotals.filter((group) => group.total_minor > 0);
  const monthlyTrendGroups = data.filter_groups.filter((group) =>
    monthlyChartData.some((point) => toMinorValue((point as Record<string, unknown>)[group.key]) > 0)
  );
  const yearlyTrendGroups = data.filter_groups.filter((group) =>
    yearlyOverviewData.some((point) => toMinorValue((point as Record<string, unknown>)[group.key]) > 0)
  );
  const expenseTrendGroups = monthlyTrendGroups.length > 0 ? monthlyTrendGroups : data.filter_groups;
  const yearlyExpenseTrendGroups = yearlyTrendGroups.length > 0 ? yearlyTrendGroups : data.filter_groups;
  const insightsLargestExpenses =
    viewMode === "year" ? buildYearLargestExpenses(selectedYearMonths, yearlyDashboardsByMonth) : data.largest_expenses;
  const groupNamesByKey = filterGroupNamesByKey(data);
  const previousMonthDashboard = yearlyDashboardsByMonth.get(shiftMonthKey(month, -1));
  const primaryFilterGroup = data.filter_groups.find((group) => group.key === "day_to_day") ?? data.filter_groups[0] ?? null;
  const selectedYearExpenseTotalMinor = sumDashboardKpiForMonths(selectedYearMonths, yearlyDashboardsByMonth, "expense_total_minor");
  const previousYearExpenseTotalMinor = sumDashboardKpiForMonths(previousYearMonths, yearlyDashboardsByMonth, "expense_total_minor");
  const selectedYearIncomeTotalMinor = sumDashboardKpiForMonths(selectedYearMonths, yearlyDashboardsByMonth, "income_total_minor");
  const previousYearIncomeTotalMinor = sumDashboardKpiForMonths(previousYearMonths, yearlyDashboardsByMonth, "income_total_minor");
  const selectedYearNetTotalMinor = sumDashboardKpiForMonths(selectedYearMonths, yearlyDashboardsByMonth, "net_total_minor");
  const yearlyPrimaryFilterGroupTotalMinor = primaryFilterGroup ? sumFilterGroupForMonths(selectedYearMonths, yearlyDashboardsByMonth, primaryFilterGroup.key) : 0;
  const yearlyExpenseMonths = yearlyOverviewData.map((point) => point.expense_total_minor);
  const yearlyAverageExpenseMonthMinor = yearlyExpenseMonths.length > 0 ? Math.round(selectedYearExpenseTotalMinor / yearlyExpenseMonths.length) : 0;
  const yearlyMedianExpenseMonthMinor = median(yearlyExpenseMonths);

  function shiftSelection(step: number) {
    if (viewMode === "month") {
      if (timelineMonths.length === 0) {
        return;
      }
      const currentIndex = monthTimelineIndex >= 0 ? monthTimelineIndex : timelineMonths.length - 1;
      const nextIndex = Math.max(0, Math.min(timelineMonths.length - 1, currentIndex + step));
      const nextMonth = timelineMonths[nextIndex];
      if (nextMonth && nextMonth !== month) {
        setTimelineMonth(nextMonth);
      }
      return;
    }

    if (timelineYears.length === 0) {
      return;
    }
    const currentIndex = yearTimelineIndex >= 0 ? yearTimelineIndex : timelineYears.length - 1;
    const nextIndex = Math.max(0, Math.min(timelineYears.length - 1, currentIndex + step));
    const nextYear = timelineYears[nextIndex];
    const nextMonth = pickTimelineMonthForYear(timelineMonths, nextYear, month);
    if (nextMonth && nextMonth !== month) {
      setTimelineMonth(nextMonth);
    }
  }

  return (
    <div className="dashboard-page-layout">
      <div className="stack-lg min-w-0">
        <PageHeader
          title="Dashboard"
          description="Month and year ledger trends."
        />

        <WorkspaceSection>
            <WorkspaceToolbar className="dashboard-toolbar">
              <div className="field min-w-[220px]">
                <span>View</span>
                <div className="dashboard-view-toggle" role="tablist" aria-label="Dashboard period view">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={viewMode === "month"}
                    className={cn("dashboard-view-toggle-button", viewMode === "month" && "dashboard-view-toggle-button-active")}
                    onClick={() => setViewMode("month")}
                  >
                    Month
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={viewMode === "year"}
                    className={cn("dashboard-view-toggle-button", viewMode === "year" && "dashboard-view-toggle-button-active")}
                    onClick={() => setViewMode("year")}
                  >
                    Year
                  </button>
                </div>
              </div>
              <div className="field min-w-[180px]">
                <span>Currency</span>
                <p className="rounded-md border border-input bg-muted/30 px-3 py-2 text-sm font-medium">{data.currency_code}</p>
              </div>
            </WorkspaceToolbar>

            <div className="dashboard-tab-list" role="tablist" aria-label="Dashboard sections">
              {DASHBOARD_TABS.map((tab) => (
                <Button
                  key={tab.id}
                  id={`dashboard-tab-${tab.id}`}
                  role="tab"
                  aria-controls={`dashboard-panel-${tab.id}`}
                  aria-selected={activeTab === tab.id}
                  variant={activeTab === tab.id ? "default" : "outline"}
                  size="sm"
                  className={cn("dashboard-tab-button", activeTab === tab.id ? "dashboard-tab-active" : "")}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </Button>
              ))}
            </div>

            <p className="muted">{DASHBOARD_TABS.find((tab) => tab.id === activeTab)?.description}</p>
        </WorkspaceSection>

        {activeTab === "overview" ? (
        <section className="stack-lg" role="tabpanel" id="dashboard-panel-overview" aria-labelledby="dashboard-tab-overview">
          {viewMode === "month" ? (
            <>
              <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatBlock label="Expense" value={formatMinor(data.kpis.expense_total_minor, data.currency_code)} tone="warning" />
                <StatBlock label="Income" value={formatMinor(data.kpis.income_total_minor, data.currency_code)} tone="success" />
                <StatBlock label="Net" value={formatMinor(data.kpis.net_total_minor, data.currency_code)} />
                <StatBlock
                  label={primaryFilterGroup ? primaryFilterGroup.name : "Primary group"}
                  value={primaryFilterGroup ? formatMinor(primaryFilterGroup.total_minor, data.currency_code) : "-"}
                />
              </section>

              <section className="grid gap-4 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <CardHeader>
                    <CardTitle>Income vs Expense Trend</CardTitle>
                  </CardHeader>
                  <CardContent className="h-80 min-w-0">
                    <DashboardChartContainer>
                      {({ width, height }) => (
                        <BarChart width={width} height={height} data={monthlyChartData}>
                          <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                          <XAxis dataKey="month" />
                          <YAxis tickFormatter={axisTick} />
                          <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                          <Legend />
                          <Bar dataKey="income_total_minor" name="Income" fill={CHART_COLORS.income} />
                          {expenseTrendGroups.map((group, index) => (
                            <Bar
                              key={group.key}
                              dataKey={group.key}
                              name={group.name}
                              stackId="expense-trend"
                              fill={dashboardBarColor(index)}
                            />
                          ))}
                        </BarChart>
                      )}
                    </DashboardChartContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Expense by Filter Group</CardTitle>
                  </CardHeader>
                  <CardContent className="h-80 min-w-0">
                    {displayGroups.length === 0 ? (
                      <p className="muted">No classified expense activity this month.</p>
                    ) : (
                        <DashboardChartContainer>
                          {({ width, height }) => (
                            <PieChart width={width} height={height}>
                              <Pie
                                data={displayGroups}
                                dataKey="total_minor"
                                nameKey="name"
                                innerRadius={56}
                                outerRadius={90}
                                paddingAngle={4}
                                {...DASHBOARD_PIE_ANIMATION_PROPS}
                              >
                                {displayGroups.map((group, index) => (
                                  <Cell key={group.key} fill={dashboardPieColor(index)} />
                                ))}
                              </Pie>
                            <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                            <Legend />
                          </PieChart>
                        )}
                      </DashboardChartContainer>
                    )}
                  </CardContent>
                </Card>
              </section>

              <Card>
                <CardHeader>
                  <CardTitle>Projection (Current Month)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-2 md:grid-cols-3">
                    <p className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm">
                      <span className="block text-xs text-muted-foreground">Spent to date</span>
                      <strong>{formatMinor(data.projection.spent_to_date_minor, data.currency_code)}</strong>
                    </p>
                    <p className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm">
                      <span className="block text-xs text-muted-foreground">Projected total</span>
                      <strong>
                        {data.projection.projected_total_minor === null
                          ? "Not a current month"
                          : formatMinor(data.projection.projected_total_minor, data.currency_code)}
                      </strong>
                    </p>
                    <p className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-sm">
                      <span className="block text-xs text-muted-foreground">Projected remaining</span>
                      <strong>
                        {data.projection.projected_remaining_minor === null
                          ? "-"
                          : formatMinor(data.projection.projected_remaining_minor, data.currency_code)}
                      </strong>
                    </p>
                  </div>

                  <div className="rounded-lg border border-border/70">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Filter group</TableHead>
                          <TableHead>Projected total</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.filter_groups.map((group) => (
                          <TableRow key={group.key}>
                            <TableCell>{group.name}</TableCell>
                            <TableCell>
                              {data.projection.projected_total_minor === null
                                ? "-"
                                : formatMinor(data.projection.projected_filter_group_totals[group.key] ?? 0, data.currency_code)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <>
              <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <StatBlock label={`${selectedYear} expense`} value={formatMinor(selectedYearExpenseTotalMinor, data.currency_code)} tone="warning" />
                <StatBlock label={`${selectedYear} income`} value={formatMinor(selectedYearIncomeTotalMinor, data.currency_code)} tone="success" />
                <StatBlock label={`${selectedYear} net`} value={formatMinor(selectedYearNetTotalMinor, data.currency_code)} />
                <StatBlock
                  label={primaryFilterGroup ? `${primaryFilterGroup.name} (${selectedYear})` : "Primary group"}
                  value={primaryFilterGroup ? formatMinor(yearlyPrimaryFilterGroupTotalMinor, data.currency_code) : "-"}
                />
              </section>

              <section className="grid gap-4 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <CardHeader>
                    <CardTitle>{selectedYear} Income vs Expense Trend</CardTitle>
                  </CardHeader>
                  <CardContent className="h-80 min-w-0">
                    {yearlyQueriesLoading ? (
                      <p className="muted">Loading yearly trend...</p>
                    ) : yearlyQueryError ? (
                      <p className="error">Failed to load yearly trend: {yearlyQueryError.message}</p>
                    ) : (
                      <DashboardChartContainer>
                        {({ width, height }) => (
                          <BarChart width={width} height={height} data={yearlyOverviewData}>
                            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                            <XAxis dataKey="month" />
                            <YAxis tickFormatter={axisTick} />
                            <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                            <Legend />
                            <Bar dataKey="income_total_minor" name="Income" fill={CHART_COLORS.income} />
                            {yearlyExpenseTrendGroups.map((group, index) => (
                              <Bar
                                key={group.key}
                                dataKey={group.key}
                                name={group.name}
                                stackId="yearly-expense-trend"
                                fill={dashboardBarColor(index)}
                              />
                            ))}
                          </BarChart>
                        )}
                      </DashboardChartContainer>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>{selectedYear} Expense by Filter Group</CardTitle>
                  </CardHeader>
                  <CardContent className="h-80 min-w-0">
                    {yearlyQueriesLoading ? (
                      <p className="muted">Loading yearly groups...</p>
                    ) : yearlyQueryError ? (
                      <p className="error">Failed to load yearly groups: {yearlyQueryError.message}</p>
                    ) : yearlyDisplayGroups.length === 0 ? (
                      <p className="muted">No classified expense activity this year.</p>
                    ) : (
                      <DashboardChartContainer>
                        {({ width, height }) => (
                          <BarChart width={width} height={height} data={yearlyDisplayGroups} layout="vertical" margin={{ left: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                            <XAxis type="number" tickFormatter={axisTick} />
                            <YAxis dataKey="name" type="category" width={132} />
                            <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                            <Bar dataKey="total_minor" name="Total" radius={[0, 6, 6, 0]}>
                              {yearlyDisplayGroups.map((group, index) => (
                                <Cell key={group.key} fill={dashboardBarColor(index)} />
                              ))}
                            </Bar>
                          </BarChart>
                        )}
                      </DashboardChartContainer>
                    )}
                  </CardContent>
                </Card>
              </section>

              <Card>
                <CardHeader>
                  <CardTitle>{selectedYear} Filter Group Monthly Bars</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="muted text-sm">Each saved filter group gets its own month-by-month bar chart for the selected year.</p>
                  {yearlyQueriesLoading ? (
                    <p className="muted">Loading filter-group yearly bars...</p>
                  ) : yearlyQueryError ? (
                    <p className="error">Failed to load filter-group yearly bars: {yearlyQueryError.message}</p>
                  ) : (
                    <div className="grid gap-4 xl:grid-cols-2">
                      {data.filter_groups.map((group, index) => {
                        const groupYearData = selectedYearMonths.map((monthKey) => ({
                          month: formatMonthShort(monthKey),
                          total_minor: filterGroupTotalForMonth(yearlyDashboardsByMonth.get(monthKey), group.key)
                        }));
                        return (
                          <div key={group.key} className="rounded-xl border border-border/70 p-4">
                            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <p className="font-medium">{group.name}</p>
                                <p className="muted text-xs">{selectedYear}</p>
                              </div>
                              <Badge variant="outline" style={{ borderColor: dashboardBarColor(index), color: dashboardBarColor(index) }}>
                                {formatMinor(sumFilterGroupForMonths(selectedYearMonths, yearlyDashboardsByMonth, group.key), data.currency_code)}
                              </Badge>
                            </div>
                            <div className="h-56 min-w-0">
                              <DashboardChartContainer>
                                {({ width, height }) => (
                                  <BarChart width={width} height={height} data={groupYearData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                                    <XAxis dataKey="month" />
                                    <YAxis tickFormatter={axisTick} />
                                    <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                                    <Bar dataKey="total_minor" name={group.name} fill={dashboardBarColor(index)} radius={[4, 4, 0, 0]} />
                                  </BarChart>
                                )}
                              </DashboardChartContainer>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </section>
      ) : null}

      {activeTab === "daily" ? (
        <section className="stack-lg" role="tabpanel" id="dashboard-panel-daily" aria-labelledby="dashboard-tab-daily">
          {viewMode === "month" ? (
            <>
              <section className="grid gap-4 md:grid-cols-3">
                <StatBlock label="Average spend day" value={formatMinor(data.kpis.average_expense_day_minor, data.currency_code)} />
                <StatBlock label="Median spend day" value={formatMinor(data.kpis.median_expense_day_minor, data.currency_code)} />
                <StatBlock label="Tracked groups" value={data.filter_groups.length} />
              </section>

              <Card>
                <CardHeader>
                  <CardTitle>Daily Spending by Filter Group</CardTitle>
                </CardHeader>
                <CardContent className="h-80 min-w-0">
                  <DashboardChartContainer>
                    {({ width, height }) => (
                      <AreaChart width={width} height={height} data={dailyChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                        <XAxis dataKey="date" />
                        <YAxis tickFormatter={axisTick} />
                        <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                        <Legend />
                        {data.filter_groups.map((group, index) => (
                          <Area
                            key={group.key}
                            type="monotone"
                            dataKey={group.key}
                            name={group.name}
                            stackId="expenses"
                            stroke={dashboardBarColor(index)}
                            fill={dashboardBarColor(index)}
                            fillOpacity={0.18}
                            strokeWidth={2}
                          />
                        ))}
                      </AreaChart>
                    )}
                  </DashboardChartContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Month-over-Month Filter Group Comparison</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="muted text-sm">
                    Compare {formatMonthLong(month)} against {formatMonthLong(shiftMonthKey(month, -1))} for each saved group.
                  </p>
                  <div className="dashboard-comparison-grid">
                    {data.filter_groups.map((group, index) => {
                      const previousTotalMinor = filterGroupTotalForMonth(previousMonthDashboard, group.key);
                      const deltaMinor = group.total_minor - previousTotalMinor;
                      return (
                        <div key={group.key} className="dashboard-comparison-card">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-medium">{group.name}</p>
                              <p className="muted text-xs">{formatMonthLong(month)}</p>
                            </div>
                            <Badge variant="outline" style={{ borderColor: dashboardBarColor(index), color: dashboardBarColor(index) }}>
                              {formatMinor(group.total_minor, data.currency_code)}
                            </Badge>
                          </div>
                          <div className="grid gap-1 text-sm">
                            <p className="muted">
                              Last month: <strong>{formatMinor(previousTotalMinor, data.currency_code)}</strong>
                            </p>
                            <p className={cn("dashboard-delta", deltaMinor > 0 ? "dashboard-delta-up" : deltaMinor < 0 ? "dashboard-delta-down" : "dashboard-delta-flat")}>
                              {deltaMinor === 0 ? "No change" : `${formatDelta(deltaMinor, data.currency_code)} vs last month`}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <>
              <section className="grid gap-4 md:grid-cols-3">
                <StatBlock label="Average expense month" value={formatMinor(yearlyAverageExpenseMonthMinor, data.currency_code)} />
                <StatBlock label="Median expense month" value={formatMinor(yearlyMedianExpenseMonthMinor, data.currency_code)} />
                <StatBlock label="Tracked groups" value={data.filter_groups.length} />
              </section>

              <Card>
                <CardHeader>
                  <CardTitle>{selectedYear} Monthly Filter Group Trend</CardTitle>
                </CardHeader>
                <CardContent className="h-80 min-w-0">
                  {yearlyQueriesLoading ? (
                    <p className="muted">Loading yearly monthly trend...</p>
                  ) : yearlyQueryError ? (
                    <p className="error">Failed to load yearly monthly trend: {yearlyQueryError.message}</p>
                  ) : (
                    <DashboardChartContainer>
                      {({ width, height }) => (
                        <BarChart width={width} height={height} data={yearlyOverviewData}>
                          <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                          <XAxis dataKey="month" />
                          <YAxis tickFormatter={axisTick} />
                          <Tooltip formatter={(value, name) => tooltipAmountWithName(data.currency_code, value, name)} />
                          <Legend />
                          {data.filter_groups.map((group, index) => (
                            <Bar
                              key={group.key}
                              dataKey={group.key}
                              name={group.name}
                              stackId="yearly-group-spend"
                              fill={dashboardBarColor(index)}
                              radius={[4, 4, 0, 0]}
                            />
                          ))}
                        </BarChart>
                      )}
                    </DashboardChartContainer>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Year-over-Year Filter Group Comparison</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="muted text-sm">Compare the selected year against the prior year for each saved filter group.</p>
                  <div className="dashboard-comparison-grid">
                    {data.filter_groups.map((group, index) => {
                      const currentTotalMinor = sumFilterGroupForMonths(selectedYearMonths, yearlyDashboardsByMonth, group.key);
                      const previousTotalMinor = sumFilterGroupForMonths(previousYearMonths, yearlyDashboardsByMonth, group.key);
                      const deltaMinor = currentTotalMinor - previousTotalMinor;
                      return (
                        <div key={group.key} className="dashboard-comparison-card">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-medium">{group.name}</p>
                              <p className="muted text-xs">{selectedYear}</p>
                            </div>
                            <Badge variant="outline" style={{ borderColor: dashboardBarColor(index), color: dashboardBarColor(index) }}>
                              {formatMinor(currentTotalMinor, data.currency_code)}
                            </Badge>
                          </div>
                          <div className="grid gap-1 text-sm">
                            <p className="muted">
                              {selectedYear - 1}: <strong>{formatMinor(previousTotalMinor, data.currency_code)}</strong>
                            </p>
                            <p className={cn("dashboard-delta", deltaMinor > 0 ? "dashboard-delta-up" : deltaMinor < 0 ? "dashboard-delta-down" : "dashboard-delta-flat")}>
                              {deltaMinor === 0 ? "No change" : `${formatDelta(deltaMinor, data.currency_code)} year over year`}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </section>
      ) : null}

      {activeTab === "breakdowns" ? (
        <section className="grid gap-4 xl:grid-cols-3" role="tabpanel" id="dashboard-panel-breakdowns" aria-labelledby="dashboard-tab-breakdowns">
          {viewMode === "year" ? (
            <div className="dashboard-scope-note xl:col-span-3">
              Breakdowns remain anchored to <strong>{formatMonthLong(month)}</strong>. Use `Overview` and `Spending` for year-level trend charts.
            </div>
          ) : null}
          <Card className="xl:col-span-1">
            <CardHeader>
              <CardTitle>Spending by Tags</CardTitle>
            </CardHeader>
            <CardContent className="h-80 min-w-0">
              {data.spending_by_tag.length === 0 ? (
                <p className="muted">No expense-tag data for this month.</p>
              ) : (
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <PieChart width={width} height={height}>
                      <Pie
                        data={data.spending_by_tag}
                        dataKey="total_minor"
                        nameKey="label"
                        outerRadius={95}
                        {...DASHBOARD_PIE_ANIMATION_PROPS}
                      >
                        {data.spending_by_tag.map((item, index) => (
                          <Cell key={item.label} fill={dashboardPieColor(index)} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                      <Legend />
                    </PieChart>
                  )}
                </DashboardChartContainer>
              )}
            </CardContent>
          </Card>

          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>Spending by Destination</CardTitle>
            </CardHeader>
            <CardContent className="h-80 min-w-0">
              {data.spending_by_to.length === 0 ? (
                <p className="muted">No destination breakdown yet.</p>
              ) : (
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={data.spending_by_to} layout="vertical" margin={{ left: 24 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                      <XAxis type="number" tickFormatter={axisTick} />
                      <YAxis dataKey="label" type="category" width={140} />
                      <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                      <Bar dataKey="total_minor" name="Total" fill={CHART_COLORS.destination} radius={[0, 6, 6, 0]} />
                    </BarChart>
                  )}
                </DashboardChartContainer>
              )}
            </CardContent>
          </Card>

          <Card className="xl:col-span-3">
            <CardHeader>
              <CardTitle>Spending by Source (`from`)</CardTitle>
            </CardHeader>
            <CardContent className="h-72 min-w-0">
              {data.spending_by_from.length === 0 ? (
                <p className="muted">No source breakdown yet.</p>
              ) : (
                <DashboardChartContainer>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={data.spending_by_from}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
                      <XAxis dataKey="label" />
                      <YAxis tickFormatter={axisTick} />
                      <Tooltip formatter={(value) => tooltipAmount(data.currency_code, value)} />
                      <Bar dataKey="total_minor" name="Total" fill={CHART_COLORS.source} radius={[6, 6, 0, 0]} />
                    </BarChart>
                  )}
                </DashboardChartContainer>
              )}
            </CardContent>
          </Card>
        </section>
      ) : null}

      {activeTab === "insights" ? (
        <section className="stack-lg" role="tabpanel" id="dashboard-panel-insights" aria-labelledby="dashboard-tab-insights">
            <Card>
              <CardHeader>
              <CardTitle>{viewMode === "year" ? "Largest Expenses (Year)" : "Largest Expenses"}</CardTitle>
              </CardHeader>
            <CardContent>
              {insightsLargestExpenses.length === 0 ? (
                <p className="muted">
                  {viewMode === "year" ? "No expense entries in this selected year." : "No expense entries in this month."}
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Groups</TableHead>
                      <TableHead>Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {insightsLargestExpenses.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell>{entry.occurred_at}</TableCell>
                        <TableCell>{entry.name}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {entry.matching_filter_group_keys.length > 0 ? (
                              entry.matching_filter_group_keys.map((key) => (
                                <Badge key={key} variant="outline">
                                  {groupNamesByKey.get(key) ?? key}
                                </Badge>
                              ))
                            ) : (
                              <Badge variant="outline">Unmatched</Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{formatMinor(entry.amount_minor, data.currency_code)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </section>
      ) : null}

      </div>

      <aside className="dashboard-page-rail">
        <div className="dashboard-timeline-panel">
          <div className="dashboard-timeline-viewport">
            <div
              ref={timelineScrollRef}
              className="dashboard-month-timeline dashboard-month-timeline-vertical"
              aria-label={viewMode === "month" ? "Month timeline" : "Year timeline"}
              onWheel={handleTimelineWheel}
              onKeyDown={handleTimelineKeyDown}
              tabIndex={0}
            >
              {(viewMode === "month" ? timelineMonths.length === 0 : timelineYears.length === 0) ? (
                <div className="dashboard-timeline-empty">
                  No expense {viewMode === "month" ? "months" : "years"} yet.
                </div>
              ) : viewMode === "month"
                ? timelineMonths.map((monthKey) => {
                    const isActive = monthKey === month;
                    return (
                      <button
                        key={monthKey}
                        ref={(node) => registerTimelineItem(monthKey, node)}
                        type="button"
                        className={cn("dashboard-month-chip", isActive && "dashboard-month-chip-active")}
                        onClick={() => setTimelineMonth(monthKey)}
                        aria-pressed={isActive}
                      >
                        <span className="dashboard-month-chip-label">{formatMonthShort(monthKey)}</span>
                        <span className="dashboard-month-chip-year">
                          {monthKey.endsWith("-01") || isActive ? formatMonthLong(monthKey) : monthKey.slice(0, 4)}
                        </span>
                      </button>
                    );
                  })
                : timelineYears.map((yearKey) => {
                    const isActive = yearKey === String(selectedYear);
                    return (
                      <button
                        key={yearKey}
                        ref={(node) => registerTimelineItem(yearKey, node)}
                        type="button"
                        className={cn("dashboard-month-chip", isActive && "dashboard-month-chip-active")}
                        onClick={() => {
                          const nextMonth = pickTimelineMonthForYear(timelineMonths, yearKey, month);
                          if (nextMonth) {
                            setTimelineMonth(nextMonth);
                          }
                        }}
                        aria-pressed={isActive}
                      >
                        <span className="dashboard-month-chip-label">{yearKey}</span>
                        <span className="dashboard-month-chip-year">{`${yearKey} overview`}</span>
                      </button>
                    );
                  })}
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
