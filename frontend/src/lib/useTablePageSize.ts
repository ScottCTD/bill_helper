/**
 * CALLING SPEC:
 * - Purpose: provide the `useTablePageSize` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/lib/useTablePageSize.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useTablePageSize`.
 * - Side effects: client-side state coordination and query wiring.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const ROW_HEIGHT = 41; // px – matches .entries-table tbody td py-2 + content
const PAGINATION_BAR_HEIGHT = 48; // px – height reserved for the pagination controls

/**
 * Measures the container element and returns how many table rows fit
 * without vertical scrolling. The table header and pagination bar heights
 * are subtracted from the available space.
 *
 * Returns `{ containerRef, pageSize }`.
 * Attach `containerRef` to the element whose height represents the
 * available space for the table body + pagination bar.
 */
export function useTablePageSize(headerHeight = 37) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pageSize, setPageSize] = useState(20); // sensible default

  const recalc = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const available = el.clientHeight - headerHeight - PAGINATION_BAR_HEIGHT;
    const rows = Math.max(1, Math.floor(available / ROW_HEIGHT));
    setPageSize(rows);
  }, [headerHeight]);

  useEffect(() => {
    recalc();
    const ro = new ResizeObserver(recalc);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [recalc]);

  return { containerRef, pageSize };
}
