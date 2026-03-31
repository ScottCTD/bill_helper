/**
 * CALLING SPEC:
 * - Purpose: render the dashboard month/year scope as a horizontal strip in the toolbar between View and Currency.
 * - Inputs: view mode, selected scope, timeline keys, scroll ref, registration callback, and month change handler.
 * - Outputs: focusable scroll region with chip buttons (newest toward the trailing edge; scroll back for older).
 * - Side effects: wheel on the strip maps to horizontal scroll and never chains to page scroll (non-passive listener); React refs via `registerTimelineItem`.
 */

import { useCallback, useRef, type KeyboardEvent, type MutableRefObject } from "react";

import { cn } from "../../lib/utils";
import { type DashboardViewMode, formatMonthLong, formatMonthShort, pickTimelineMonthForYear } from "./helpers";

type DashboardTimelineStripProps = {
  viewMode: DashboardViewMode;
  month: string;
  selectedYear: number;
  timelineMonths: string[];
  timelineYears: string[];
  timelineScrollRef: MutableRefObject<HTMLDivElement | null>;
  registerTimelineItem: (key: string, node: HTMLButtonElement | null) => void;
  setTimelineMonth: (nextMonth: string, behavior?: ScrollBehavior) => void;
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => void;
};

/** Normalize wheel delta to CSS pixels (handles line/page modes). */
function wheelAxisPixels(e: WheelEvent, axis: "x" | "y"): number {
  const raw = axis === "y" ? e.deltaY : e.deltaX;
  if (e.deltaMode === 1) {
    return raw * 16;
  }
  if (e.deltaMode === 2) {
    const page = axis === "y" ? window.innerHeight : window.innerWidth;
    return raw * (page || 800);
  }
  return raw;
}

/** Wheel over the strip scrolls horizontally and does not scroll the page, including at scroll extents. */
function attachTimelineStripWheel(el: HTMLElement): () => void {
  const onWheel = (e: WheelEvent) => {
    e.preventDefault();

    const py = wheelAxisPixels(e, "y");
    const px = wheelAxisPixels(e, "x");
    // Prefer vertical delta when tied or dominant so trackpads that skew deltaX still scroll months.
    const delta = Math.abs(py) >= Math.abs(px) ? py : px;
    el.scrollBy({ left: delta, behavior: "auto" });
  };

  el.addEventListener("wheel", onWheel, { passive: false });
  return () => el.removeEventListener("wheel", onWheel);
}

/** Two-digit year from `YYYY-MM` for compact toolbar chips. */
function shortYearFromMonthKey(monthKey: string): string {
  return monthKey.slice(2, 4);
}

export function DashboardTimelineStrip({
  viewMode,
  month,
  selectedYear,
  timelineMonths,
  timelineYears,
  timelineScrollRef,
  registerTimelineItem,
  setTimelineMonth,
  onKeyDown
}: DashboardTimelineStripProps) {
  const empty =
    viewMode === "month" ? timelineMonths.length === 0 : timelineYears.length === 0;

  const wheelCleanupRef = useRef<(() => void) | null>(null);

  const setStripRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (wheelCleanupRef.current) {
        wheelCleanupRef.current();
        wheelCleanupRef.current = null;
      }
      timelineScrollRef.current = node;
      if (node) {
        wheelCleanupRef.current = attachTimelineStripWheel(node);
      }
    },
    [timelineScrollRef]
  );

  return (
    <div className="dashboard-timeline-strip-field dashboard-toolbar-period field min-w-0">
      <span className="text-[12px] font-medium text-muted-foreground">Period</span>
      <div
        ref={setStripRef}
        className="dashboard-timeline-strip"
        aria-label={viewMode === "month" ? "Month timeline" : "Year timeline"}
        onKeyDown={onKeyDown}
        tabIndex={0}
      >
        {empty ? (
          <div className="dashboard-timeline-empty dashboard-timeline-empty-inline">
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
                className={cn(
                  "dashboard-month-chip-toolbar inline-flex items-center",
                  isActive && "dashboard-month-chip-toolbar-active"
                )}
                onClick={() => setTimelineMonth(monthKey)}
                aria-label={formatMonthLong(monthKey)}
                aria-pressed={isActive}
              >
                <span className="dashboard-month-chip-toolbar-label">
                  {formatMonthShort(monthKey)}
                  <span className="dashboard-month-chip-toolbar-sub"> ’{shortYearFromMonthKey(monthKey)}</span>
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
                className={cn(
                  "dashboard-month-chip-toolbar inline-flex items-center",
                  isActive && "dashboard-month-chip-toolbar-active"
                )}
                onClick={() => {
                  const nextMonth = pickTimelineMonthForYear(timelineMonths, yearKey, month);
                  if (nextMonth) {
                    setTimelineMonth(nextMonth);
                  }
                }}
                aria-label={`${yearKey} overview`}
                aria-pressed={isActive}
              >
                <span className="dashboard-month-chip-toolbar-label">{yearKey}</span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
