/**
 * CALLING SPEC:
 * - Purpose: render the dashboard month and year timeline selector rail.
 * - Inputs: current dashboard scope, available timeline keys, and selection handlers from the route shell.
 * - Outputs: the dashboard timeline aside.
 * - Side effects: React rendering and user event wiring only.
 */

import type { KeyboardEvent, MutableRefObject, WheelEvent } from "react";

import { cn } from "../../lib/utils";
import { type DashboardViewMode, formatMonthLong, formatMonthShort, pickTimelineMonthForYear } from "./helpers";

type DashboardTimelineRailProps = {
  viewMode: DashboardViewMode;
  month: string;
  selectedYear: number;
  timelineMonths: string[];
  timelineYears: string[];
  timelineScrollRef: MutableRefObject<HTMLDivElement | null>;
  registerTimelineItem: (key: string, node: HTMLButtonElement | null) => void;
  setTimelineMonth: (nextMonth: string) => void;
  handleTimelineWheel: (event: WheelEvent<HTMLDivElement>) => void;
  handleTimelineKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
};

export function DashboardTimelineRail({
  viewMode,
  month,
  selectedYear,
  timelineMonths,
  timelineYears,
  timelineScrollRef,
  registerTimelineItem,
  setTimelineMonth,
  handleTimelineWheel,
  handleTimelineKeyDown
}: DashboardTimelineRailProps) {
  return (
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
            ) : viewMode === "month" ? (
              timelineMonths.map((monthKey) => {
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
            ) : (
              timelineYears.map((yearKey) => {
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
              })
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
