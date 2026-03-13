# CALLING SPEC:
# - Purpose: compatibility seam re-exporting the canonical finance dashboard, reconciliation, and aggregate services.
# - Inputs: import the public symbols from this module if older callers still depend on `backend.services.finance`.
# - Outputs: the same public functions and dataclasses exposed by the canonical finance modules.
# - Side effects: none in this module; delegated to the imported canonical functions.

from __future__ import annotations

from backend.services.finance_aggregates import (
    aggregate_daily_expenses,
    aggregate_monthly_totals,
    aggregate_top_tags,
)
from backend.services.finance_dashboard import (
    DASHBOARD_DEFAULT_CURRENCY_CODE,
    DashboardAnalyticsOptions,
    DashboardFilter,
    build_dashboard_analytics,
    build_dashboard_read,
    build_dashboard_timeline_read,
    list_dashboard_expense_months,
    month_window,
)
from backend.services.finance_reconciliation import (
    build_dashboard_reconciliation_summary,
    build_reconciliation,
    list_dashboard_reconciliation_accounts,
)

__all__ = [
    "DASHBOARD_DEFAULT_CURRENCY_CODE",
    "DashboardAnalyticsOptions",
    "DashboardFilter",
    "aggregate_daily_expenses",
    "aggregate_monthly_totals",
    "aggregate_top_tags",
    "build_dashboard_analytics",
    "build_dashboard_read",
    "build_dashboard_reconciliation_summary",
    "build_dashboard_timeline_read",
    "build_reconciliation",
    "list_dashboard_expense_months",
    "list_dashboard_reconciliation_accounts",
    "month_window",
]
