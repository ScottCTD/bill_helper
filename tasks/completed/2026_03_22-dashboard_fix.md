# Dashboard fix (archived)

**Status:** completed (2026-03-22)

## Summary

- **Income vs Expense trend (month view):** Last six months anchored to the client’s current calendar month (not the timeline selection); grouped Income / Expense legend with colors in stack order; optional extra query when the selected month differs from the anchor.
- **Tab blurbs:** Removed secondary description lines under all dashboard section tabs (`DASHBOARD_TABS` labels only).
- **View / Currency toolbar:** Equal-width side columns on `sm+`, shared `h-10` control row, aligned labels; period strip between them with compact chips.
- **Month selector:** Replaced floating rail with a horizontal period strip in the toolbar (between View and Currency); wheel maps to horizontal scroll; trailing-edge scroll alignment for selection.
- **UI polish:** Removed border between chart and legend; toolbar height/visual consistency iterations.

## Original task notes

current dashboard needs few fixes.

the "Income vs Expense Trend" segmented bar plot should be fixed of the last 6 months from the current month. note that current month = the current actual month, not the currently selected month.

also it doesn't have a legend for the segments? like what filter group does each color represent? we should have 2 categories: income and expense. for each category, we should have the legend color ordered in the same order as the segments.

---

remove the text "Month snapshot, projection, and filter-group mix"

---

the "View" and "Currency" has different vertical positions, as the month-year switch and the currency box have different sizes
can you make them same size?

---

the month selector is brittle - it's now floating and overlapping with the page, and its behavior is not perfect
