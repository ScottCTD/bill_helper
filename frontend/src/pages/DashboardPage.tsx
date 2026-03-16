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
import { AgentCostDashboard } from "../features/dashboard/AgentCostDashboard";
import {
  DashboardBreakdownsPanel,
  DashboardDailyPanel,
  DashboardInsightsPanel,
  DashboardOverviewPanel
} from "../features/dashboard/DashboardPanels";
import { DashboardTimelineRail } from "../features/dashboard/DashboardTimelineRail";
import {
  DASHBOARD_TABS,
  TIMELINE_WHEEL_LOCK_MS,
  type DashboardTab,
  type DashboardViewMode,
  buildDailyChartData,
  buildMonthlyChartData,
  buildTimelineYears,
  buildYearFilterGroupTotals,
  buildYearLargestExpenses,
  buildYearMonthKeys,
  buildYearlyOverviewData,
  filterGroupNamesByKey,
  median,
  pickTimelineMonthForYear,
  shiftMonthKey,
  sumDashboardKpiForMonths,
  sumFilterGroupForMonths
} from "../features/dashboard/helpers";
import { getDashboard, getDashboardTimeline } from "../lib/api";
import { currentMonth } from "../lib/format";
import { queryKeys } from "../lib/queryKeys";
import type { Dashboard } from "../lib/types";
import { cn } from "../lib/utils";

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
  const chartGroups = data.filter_groups.filter((group) => group.total_minor > 0);
  const displayGroups = chartGroups.length > 0 ? chartGroups : data.filter_groups;
  const dailyChartData = buildDailyChartData(data);
  const monthlyChartData = buildMonthlyChartData(data);
  const yearlyOverviewData = buildYearlyOverviewData(selectedYearMonths, yearlyDashboardsByMonth, data.filter_groups);
  const yearlyFilterGroupTotals = buildYearFilterGroupTotals(data.filter_groups, selectedYearMonths, yearlyDashboardsByMonth);
  const yearlyDisplayGroups = yearlyFilterGroupTotals.filter((group) => group.total_minor > 0);
  const monthlyTrendGroups = data.filter_groups.filter((group) =>
    monthlyChartData.some((point) => Number((point as Record<string, unknown>)[group.key] ?? 0) > 0)
  );
  const yearlyTrendGroups = data.filter_groups.filter((group) =>
    yearlyOverviewData.some((point) => Number((point as Record<string, unknown>)[group.key] ?? 0) > 0)
  );
  const expenseTrendGroups = monthlyTrendGroups.length > 0 ? monthlyTrendGroups : data.filter_groups;
  const yearlyExpenseTrendGroups = yearlyTrendGroups.length > 0 ? yearlyTrendGroups : data.filter_groups;
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

  return (
    <div className="dashboard-page-layout">
      <div className="stack-lg min-w-0">
        <PageHeader title="Dashboard" description="Month and year ledger trends." />

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
            displayGroups={displayGroups}
            monthlyChartData={monthlyChartData}
            expenseTrendGroups={expenseTrendGroups}
            primaryFilterGroup={primaryFilterGroup}
            yearlyQueriesLoading={yearlyQueriesLoading}
            yearlyQueryError={yearlyQueryError}
            yearlyOverviewData={yearlyOverviewData}
            yearlyDisplayGroups={yearlyDisplayGroups}
            yearlyExpenseTrendGroups={yearlyExpenseTrendGroups}
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
