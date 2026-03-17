/**
 * CALLING SPEC:
 * - Purpose: orchestrate dashboard queries, scope selection, and tab routing for the dashboard page.
 * - Inputs: dashboard API queries, route-local selection state, and dashboard feature panel components.
 * - Outputs: the dashboard page shell with derived monthly and yearly view models.
 * - Side effects: dashboard data fetching and UI event wiring.
 */

import { useEffect, useRef, useState, type KeyboardEvent, type WheelEvent } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { WorkspaceToolbar } from "../components/layout/WorkspaceToolbar";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { AgentCostDashboard } from "../features/dashboard/AgentCostDashboard";
import {
  DashboardBreakdownsPanel,
  DashboardDailyPanel,
  DashboardInsightsPanel,
  DashboardOverviewPanel
} from "../features/dashboard/DashboardPanels";
import { DashboardTimelineRail } from "../features/dashboard/DashboardTimelineRail";
import {
  CHART_COLORS,
  DASHBOARD_TABS,
  TIMELINE_WHEEL_LOCK_MS,
  type DashboardTab,
  type DashboardViewMode,
  DashboardChartContainer,
  axisTick,
  buildDailyChartData,
  buildMonthlyChartData,
  buildTimelineYears,
  buildYearLargestExpenses,
  buildYearMonthKeys,
  buildYearlyOverviewData,
  builtinGroupColor,
  builtinIncomeGroupColor,
  filterGroupNamesByKey,
  isIncomeFilterGroupKey,
  limitTrendDataToMonthsWithData,
  median,
  pickTimelineMonthForYear,
  shiftMonthKey,
  sortByBuiltinOrder,
  sortByIncomeBarOrder,
  sortByIncomeTrendOrder,
  sumDashboardKpiForMonths,
  sumFilterGroupForMonths,
  tooltipAmount
} from "../features/dashboard/helpers";
import { getDashboard, getDashboardTimeline } from "../lib/api";
import { currentMonth } from "../lib/format";
import { queryKeys } from "../lib/queryKeys";
import type { Dashboard } from "../lib/types";
import { cn } from "../lib/utils";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

type IncomeTrendChartProps = {
  data: Array<Record<string, unknown>>;
  trendGroups: Array<{ key: string; name: string }>;
  incomeTrendGroups: Array<{ key: string; name: string }>;
  currencyCode: string;
};

function IncomeTrendChart({ data: chartData, trendGroups, incomeTrendGroups, currencyCode }: IncomeTrendChartProps) {
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  return (
    <DashboardChartContainer>
      {({ width, height }) => (
        <BarChart width={width} height={height} data={chartData} barCategoryGap="20%" barGap={4}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.muted} opacity={0.2} />
          <XAxis dataKey="month" />
          <YAxis tickFormatter={axisTick} />
          <Tooltip
            content={({ payload, label }) => {
              const active = payload?.find((p) => p.dataKey === hoveredKey) ?? payload?.[0];
              if (!active) return null;
              return (
                <div className="rounded-md border border-border bg-popover px-3 py-2 text-sm shadow-md">
                  <p className="text-muted-foreground mb-1">{String(label)}</p>
                  <p className="font-medium">{String(active.name)}: {tooltipAmount(currencyCode, active.value)}</p>
                </div>
              );
            }}
          />
          {incomeTrendGroups.map((group) => (
            <Bar
              key={group.key}
              dataKey={group.key}
              name={group.name}
              stackId="income"
              fill={builtinIncomeGroupColor(group.key)}
              onMouseEnter={() => setHoveredKey(group.key)}
            />
          ))}
          {trendGroups.map((group) => (
            <Bar
              key={group.key}
              dataKey={group.key}
              name={group.name}
              stackId="expense-trend"
              fill={builtinGroupColor(group.key)}
              onMouseEnter={() => setHoveredKey(group.key)}
            />
          ))}
        </BarChart>
      )}
    </DashboardChartContainer>
  );
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
  const dashboardQuery = useQuery({
    queryKey: queryKeys.dashboard.month(month),
    queryFn: () => getDashboard(month)
  });

  const timelineMonths = timelineQuery.data?.months ?? [];
  const timelineYears = buildTimelineYears(timelineMonths);
  const selectedYear = Number(month.slice(0, 4));
  const selectedYearMonths = buildYearMonthKeys(selectedYear);
  const previousYearMonths = buildYearMonthKeys(selectedYear - 1);
  const yearlyMonthKeys = [...previousYearMonths, ...selectedYearMonths];

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
      timelineScroller.scrollTo({ top: timelineScroller.scrollTop + delta, behavior });
      return;
    }

    const delta = itemRect.left + itemRect.width / 2 - (scrollerRect.left + scrollerRect.width / 2);
    timelineScroller.scrollTo({ left: timelineScroller.scrollLeft + delta, behavior });
  }

  function registerTimelineItem(key: string, node: HTMLButtonElement | null) {
    if (!node) {
      timelineItemRefs.current.delete(key);
      return;
    }
    timelineItemRefs.current.set(key, node);
  }

  function shiftSelection(step: number) {
    if (viewMode === "month") {
      if (timelineMonths.length === 0) {
        return;
      }
      const currentIndex = monthTimelineIndex >= 0 ? monthTimelineIndex : timelineMonths.length - 1;
      const nextMonth = timelineMonths[Math.max(0, Math.min(timelineMonths.length - 1, currentIndex + step))];
      if (nextMonth && nextMonth !== month) {
        setTimelineMonth(nextMonth);
      }
      return;
    }

    if (timelineYears.length === 0) {
      return;
    }
    const currentIndex = yearTimelineIndex >= 0 ? yearTimelineIndex : timelineYears.length - 1;
    const nextYear = timelineYears[Math.max(0, Math.min(timelineYears.length - 1, currentIndex + step))];
    const nextMonth = pickTimelineMonthForYear(timelineMonths, nextYear, month);
    if (nextMonth && nextMonth !== month) {
      setTimelineMonth(nextMonth);
    }
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

    const frame = requestAnimationFrame(() => {
      centerTimelineItem(selectedItem, behavior);
    });

    return () => {
      cancelAnimationFrame(frame);
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

  const yearlyQueriesLoading = yearlyQueries.some((query) => query.isLoading);
  const yearlyQueryError = yearlyQueries.find((query) => query.isError)?.error as Error | undefined;
  const dailyChartData = buildDailyChartData(data);
  const monthlyChartData = buildMonthlyChartData(data);
  const yearlyOverviewData = buildYearlyOverviewData(selectedYearMonths, yearlyDashboardsByMonth, data.filter_groups);

  // Trend chart: expense groups (exclude income groups) and income groups
  const sortedFilterGroups = sortByBuiltinOrder(data.filter_groups);
  const expenseGroups = sortedFilterGroups.filter((g) => !isIncomeFilterGroupKey(g.key));
  const incomeGroups = sortedFilterGroups.filter((g) => isIncomeFilterGroupKey(g.key));
  const monthlyExpenseTrendGroups = expenseGroups.filter((group) =>
    monthlyChartData.some((point) => Number((point as Record<string, unknown>)[group.key] ?? 0) > 0)
  );
  const expenseTrendGroups = monthlyExpenseTrendGroups.length > 0 ? monthlyExpenseTrendGroups : expenseGroups;
  const yearlyExpenseTrendGroupsRaw = expenseGroups.filter((group) =>
    yearlyOverviewData.some((point) => Number((point as Record<string, unknown>)[group.key] ?? 0) > 0)
  );
  const yearlyExpenseTrendGroups = yearlyExpenseTrendGroupsRaw.length > 0 ? yearlyExpenseTrendGroupsRaw : expenseGroups;
  const monthlyIncomeTrendGroups = incomeGroups.filter((group) =>
    monthlyChartData.some((point) => Number((point as Record<string, unknown>)[group.key] ?? 0) > 0)
  );
  const incomeTrendGroups = sortByIncomeBarOrder(
    monthlyIncomeTrendGroups.length > 0 ? monthlyIncomeTrendGroups : incomeGroups
  );

  const insightsLargestExpenses =
    viewMode === "year" ? buildYearLargestExpenses(selectedYearMonths, yearlyDashboardsByMonth) : data.largest_expenses;
  const groupNamesByKey = filterGroupNamesByKey(data);
  const previousMonthDashboard = yearlyDashboardsByMonth.get(shiftMonthKey(month, -1));
  const primaryFilterGroup = data.filter_groups.find((group) => group.key === "day_to_day") ?? data.filter_groups[0] ?? null;
  const selectedYearExpenseTotalMinor = sumDashboardKpiForMonths(selectedYearMonths, yearlyDashboardsByMonth, "expense_total_minor");
  const selectedYearIncomeTotalMinor = sumDashboardKpiForMonths(selectedYearMonths, yearlyDashboardsByMonth, "income_total_minor");
  const selectedYearNetTotalMinor = sumDashboardKpiForMonths(selectedYearMonths, yearlyDashboardsByMonth, "net_total_minor");
  const yearlyPrimaryFilterGroupTotalMinor = primaryFilterGroup
    ? sumFilterGroupForMonths(selectedYearMonths, yearlyDashboardsByMonth, primaryFilterGroup.key)
    : 0;
  const yearlyExpenseMonths = yearlyOverviewData.map((point) => point.expense_total_minor);
  const yearlyAverageExpenseMonthMinor =
    yearlyExpenseMonths.length > 0 ? Math.round(selectedYearExpenseTotalMinor / yearlyExpenseMonths.length) : 0;
  const yearlyMedianExpenseMonthMinor = median(yearlyExpenseMonths);

  const trendChartData =
    viewMode === "month" ? limitTrendDataToMonthsWithData(monthlyChartData) : yearlyOverviewData;
  const expenseOnlyGroups = sortedFilterGroups.filter((g) => !isIncomeFilterGroupKey(g.key));
  const expenseTrendGroupsFiltered =
    viewMode === "month"
      ? (monthlyExpenseTrendGroups.length > 0 ? monthlyExpenseTrendGroups : expenseOnlyGroups).filter(
          (g) => !isIncomeFilterGroupKey(g.key)
        )
      : (yearlyExpenseTrendGroupsRaw.length > 0 ? yearlyExpenseTrendGroupsRaw : expenseOnlyGroups).filter(
          (g) => !isIncomeFilterGroupKey(g.key)
        );
  const trendGroups = sortByIncomeTrendOrder(viewMode === "month" ? expenseTrendGroupsFiltered : expenseTrendGroupsFiltered);
  const trendTitle = viewMode === "month" ? "Income vs Expense Trend" : `${selectedYear} Income vs Expense Trend`;

  return (
    <div className="dashboard-page-layout">
      <div className="stack-lg min-w-0">
        <PageHeader title="Dashboard" description="Month and year ledger trends." />

        <Card>
          <CardHeader>
            <CardTitle>{trendTitle}</CardTitle>
          </CardHeader>
          <CardContent className="h-72 min-w-0">
            {viewMode === "year" && yearlyQueriesLoading ? (
              <p className="muted text-sm">Loading yearly trend...</p>
            ) : (
              <IncomeTrendChart
                data={trendChartData}
                trendGroups={trendGroups}
                incomeTrendGroups={incomeTrendGroups}
                currencyCode={data.currency_code}
              />
            )}
          </CardContent>
        </Card>

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
          <DashboardOverviewPanel
            viewMode={viewMode}
            selectedYear={selectedYear}
            data={data}
            primaryFilterGroup={primaryFilterGroup}
            yearlyQueriesLoading={yearlyQueriesLoading}
            yearlyQueryError={yearlyQueryError}
            selectedYearExpenseTotalMinor={selectedYearExpenseTotalMinor}
            selectedYearIncomeTotalMinor={selectedYearIncomeTotalMinor}
            selectedYearNetTotalMinor={selectedYearNetTotalMinor}
            yearlyPrimaryFilterGroupTotalMinor={yearlyPrimaryFilterGroupTotalMinor}
            selectedYearMonths={selectedYearMonths}
            yearlyDashboardsByMonth={yearlyDashboardsByMonth}
          />
        ) : null}

        {activeTab === "daily" ? (
          <DashboardDailyPanel
            viewMode={viewMode}
            selectedYear={selectedYear}
            data={data}
            dailyChartData={dailyChartData}
            month={month}
            previousMonthDashboard={previousMonthDashboard}
            yearlyQueriesLoading={yearlyQueriesLoading}
            yearlyQueryError={yearlyQueryError}
            yearlyOverviewData={yearlyOverviewData}
            yearlyAverageExpenseMonthMinor={yearlyAverageExpenseMonthMinor}
            yearlyMedianExpenseMonthMinor={yearlyMedianExpenseMonthMinor}
            selectedYearMonths={selectedYearMonths}
            previousYearMonths={previousYearMonths}
            yearlyDashboardsByMonth={yearlyDashboardsByMonth}
          />
        ) : null}

        {activeTab === "breakdowns" ? <DashboardBreakdownsPanel viewMode={viewMode} month={month} data={data} /> : null}

        {activeTab === "insights" ? (
          <DashboardInsightsPanel
            viewMode={viewMode}
            selectedYear={selectedYear}
            month={month}
            data={data}
            insightsLargestExpenses={insightsLargestExpenses}
            groupNamesByKey={groupNamesByKey}
          />
        ) : null}

        {activeTab === "agent" ? <AgentCostDashboard /> : null}
      </div>

      <DashboardTimelineRail
        viewMode={viewMode}
        month={month}
        selectedYear={selectedYear}
        timelineMonths={timelineMonths}
        timelineYears={timelineYears}
        timelineScrollRef={timelineScrollRef}
        registerTimelineItem={registerTimelineItem}
        setTimelineMonth={setTimelineMonth}
        handleTimelineWheel={handleTimelineWheel}
        handleTimelineKeyDown={handleTimelineKeyDown}
      />
    </div>
  );
}
