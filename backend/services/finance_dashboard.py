# CALLING SPEC:
# - Purpose: dashboard window queries, expense analytics, and dashboard read-model orchestration.
# - Inputs: SQLAlchemy session, scoped principal filters, month windows, runtime settings, and filter group definitions.
# - Outputs: dashboard read models, dashboard timeline reads, and dashboard analytics payloads.
# - Side effects: reads database state only.

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from backend.auth.contracts import RequestPrincipal
from backend.enums_finance import EntryKind
from backend.models_finance import Account, Entry
from backend.schemas_finance import (
    DashboardBreakdownItem,
    DashboardDailySpendingPoint,
    DashboardFilterGroupSummary,
    DashboardKpisRead,
    DashboardLargestExpenseItem,
    DashboardMonthlyTrendPoint,
    DashboardProjectionRead,
    DashboardRead,
    DashboardTimelineRead,
    DashboardWeekdaySpendingPoint,
)
from backend.services.access_scope import account_owner_filter, entry_owner_filter
from backend.services.filter_groups import (
    FilterGroupDefinition,
    build_filter_entry_context,
    list_filter_group_definitions,
    matching_filter_group_keys,
)
from backend.services.finance_reconciliation import (
    build_dashboard_reconciliation_summary,
    build_reconciliation,
    list_dashboard_reconciliation_accounts,
)
from backend.services.runtime_settings import resolve_runtime_settings

DASHBOARD_DEFAULT_CURRENCY_CODE = "CAD"
WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DashboardFilter = ColumnElement[bool]


@dataclass(slots=True)
class _ExpenseAnalyticsRollup:
    expense_totals_by_date: dict[date, int]
    filter_group_totals_by_date: dict[date, dict[str, int]]
    filter_group_totals: dict[str, int]
    spending_by_from: dict[str, int]
    spending_by_to: dict[str, int]
    spending_by_tag: dict[str, int]
    weekday_totals: dict[int, int]
    largest_expenses: list[DashboardLargestExpenseItem]


@dataclass(frozen=True, slots=True)
class DashboardAnalyticsOptions:
    currency_code: str = DASHBOARD_DEFAULT_CURRENCY_CODE
    trend_months: int = 6
    today: date | None = None
    entry_filter: DashboardFilter | None = None
    account_filter: DashboardFilter | None = None


def month_window(month: str) -> tuple[date, date]:
    year, month_num = map(int, month.split("-"))
    start = date(year, month_num, 1)
    if month_num == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month_num + 1, 1)
    return start, end


def build_dashboard_read(
    db: Session,
    *,
    month: str,
    principal: RequestPrincipal,
) -> DashboardRead:
    start, end = month_window(month)

    runtime_settings = resolve_runtime_settings(db)
    dashboard_currency_code = runtime_settings.dashboard_currency_code
    filter_groups = list_filter_group_definitions(db, principal=principal)

    analytics = build_dashboard_analytics(
        db,
        start=start,
        end=end,
        options=DashboardAnalyticsOptions(
            currency_code=dashboard_currency_code,
            entry_filter=entry_owner_filter(principal),
            account_filter=account_owner_filter(principal),
        ),
        filter_groups=filter_groups,
    )

    as_of = min(date.today(), end - timedelta(days=1))
    accounts = list_dashboard_reconciliation_accounts(
        db,
        currency_code=dashboard_currency_code,
        principal=principal,
    )
    reconciliation = [
        build_dashboard_reconciliation_summary(build_reconciliation(db, account, as_of))
        for account in accounts
    ]

    return DashboardRead(
        month=month,
        currency_code=dashboard_currency_code,
        **analytics,
        reconciliation=reconciliation,
    )


def build_dashboard_timeline_read(
    db: Session,
    *,
    principal: RequestPrincipal,
) -> DashboardTimelineRead:
    runtime_settings = resolve_runtime_settings(db)
    dashboard_currency_code = runtime_settings.dashboard_currency_code
    months = list_dashboard_expense_months(
        db,
        currency_code=dashboard_currency_code,
        principal=principal,
    )
    return DashboardTimelineRead(months=months)


def _shift_month(month_start: date, month_delta: int) -> date:
    normalized_month_index = (month_start.year * 12) + (month_start.month - 1) + month_delta
    year = normalized_month_index // 12
    month = (normalized_month_index % 12) + 1
    return date(year, month, 1)


def _normalize_breakdown_label(raw_label: str | None) -> str:
    normalized = (raw_label or "").strip()
    return normalized if normalized else "(unspecified)"


def _account_entity_ids(
    db: Session,
    *,
    account_filter: DashboardFilter | None = None,
) -> set[str]:
    linked_accounts_stmt = select(Account.id)
    if account_filter is not None:
        linked_accounts_stmt = linked_accounts_stmt.where(account_filter)
    return {entity_id for entity_id in db.scalars(linked_accounts_stmt).all() if entity_id}


def _is_internal_account_transfer(entry: Entry, account_entity_ids: set[str]) -> bool:
    return (
        entry.from_entity_id is not None
        and entry.to_entity_id is not None
        and entry.from_entity_id in account_entity_ids
        and entry.to_entity_id in account_entity_ids
    )


def _list_entries_for_window(
    db: Session,
    start: date,
    end: date,
    currency_code: str,
    *,
    entry_filter: DashboardFilter | None = None,
) -> list[Entry]:
    stmt = (
        select(Entry)
        .where(
            Entry.is_deleted.is_(False),
            Entry.occurred_at >= start,
            Entry.occurred_at < end,
            Entry.currency_code == currency_code,
        )
        .options(selectinload(Entry.tags))
        .order_by(Entry.occurred_at.asc(), Entry.created_at.asc())
    )
    if entry_filter is not None:
        stmt = stmt.where(entry_filter)
    return list(db.scalars(stmt))


def list_dashboard_expense_months(
    db: Session,
    *,
    currency_code: str,
    principal: RequestPrincipal,
) -> list[str]:
    account_entity_ids = _account_entity_ids(
        db,
        account_filter=account_owner_filter(principal),
    )
    rows = db.execute(
        select(Entry.occurred_at, Entry.from_entity_id, Entry.to_entity_id)
        .where(
            Entry.is_deleted.is_(False),
            Entry.kind == EntryKind.EXPENSE,
            Entry.currency_code == currency_code.upper(),
            entry_owner_filter(principal),
        )
        .order_by(Entry.occurred_at.asc(), Entry.created_at.asc())
    ).all()

    months: list[str] = []
    seen_months: set[str] = set()
    for occurred_at, from_entity_id, to_entity_id in rows:
        if (
            from_entity_id is not None
            and to_entity_id is not None
            and from_entity_id in account_entity_ids
            and to_entity_id in account_entity_ids
        ):
            continue
        month_key = occurred_at.strftime("%Y-%m")
        if month_key in seen_months:
            continue
        seen_months.add(month_key)
        months.append(month_key)

    return months


def _build_breakdown_items(totals: dict[str, int], limit: int = 8) -> list[DashboardBreakdownItem]:
    grand_total = sum(totals.values())
    if grand_total <= 0:
        return []

    rows = sorted(totals.items(), key=lambda row: (-row[1], row[0]))[:limit]
    return [
        DashboardBreakdownItem(
            label=label,
            total_minor=total_minor,
            share=round(total_minor / grand_total, 4),
        )
        for label, total_minor in rows
    ]


def _list_non_transfer_entries_for_window(
    db: Session,
    *,
    start: date,
    end: date,
    currency_code: str,
    account_entity_ids: set[str],
    entry_filter: DashboardFilter | None = None,
) -> list[Entry]:
    return [
        entry
        for entry in _list_entries_for_window(
            db,
            start,
            end,
            currency_code,
            entry_filter=entry_filter,
        )
        if not _is_internal_account_transfer(entry, account_entity_ids)
    ]


def _matching_filter_group_keys(
    *,
    entry: Entry,
    filter_groups: list[FilterGroupDefinition],
    account_entity_ids: set[str],
) -> list[str]:
    context = build_filter_entry_context(entry, account_entity_ids=account_entity_ids)
    return matching_filter_group_keys(context=context, filter_groups=filter_groups)


def _rollup_expense_entries(
    expense_entries: list[Entry],
    *,
    filter_groups: list[FilterGroupDefinition],
    account_entity_ids: set[str],
) -> _ExpenseAnalyticsRollup:
    expense_totals_by_date: dict[date, int] = defaultdict(int)
    filter_group_totals_by_date: dict[date, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    filter_group_totals: dict[str, int] = defaultdict(int)
    spending_by_from: dict[str, int] = defaultdict(int)
    spending_by_to: dict[str, int] = defaultdict(int)
    spending_by_tag: dict[str, int] = defaultdict(int)
    weekday_totals: dict[int, int] = defaultdict(int)
    largest_expenses: list[DashboardLargestExpenseItem] = []

    for entry in expense_entries:
        amount_minor = entry.amount_minor
        expense_totals_by_date[entry.occurred_at] += amount_minor

        matching_filter_group_keys = _matching_filter_group_keys(
            entry=entry,
            filter_groups=filter_groups,
            account_entity_ids=account_entity_ids,
        )
        for key in matching_filter_group_keys:
            filter_group_totals_by_date[entry.occurred_at][key] += amount_minor
            filter_group_totals[key] += amount_minor

        spending_by_from[_normalize_breakdown_label(entry.from_entity)] += amount_minor
        spending_by_to[_normalize_breakdown_label(entry.to_entity)] += amount_minor
        weekday_totals[entry.occurred_at.weekday()] += amount_minor

        if entry.tags:
            for tag in entry.tags:
                normalized_tag = tag.name.strip().lower() if tag.name else ""
                if normalized_tag:
                    spending_by_tag[normalized_tag] += amount_minor
        else:
            spending_by_tag["(untagged)"] += amount_minor

        largest_expenses.append(
            DashboardLargestExpenseItem(
                id=entry.id,
                occurred_at=entry.occurred_at,
                name=entry.name,
                to_entity=entry.to_entity,
                amount_minor=amount_minor,
                matching_filter_group_keys=matching_filter_group_keys,
            )
        )

    return _ExpenseAnalyticsRollup(
        expense_totals_by_date=expense_totals_by_date,
        filter_group_totals_by_date=filter_group_totals_by_date,
        filter_group_totals=filter_group_totals,
        spending_by_from=spending_by_from,
        spending_by_to=spending_by_to,
        spending_by_tag=spending_by_tag,
        weekday_totals=weekday_totals,
        largest_expenses=largest_expenses,
    )


def _build_dashboard_kpis(
    *,
    rollup: _ExpenseAnalyticsRollup,
    income_total_minor: int,
) -> DashboardKpisRead:
    expense_total_minor = sum(rollup.expense_totals_by_date.values())
    expense_day_values = list(rollup.expense_totals_by_date.values())
    average_expense_day_minor = (
        int(round(sum(expense_day_values) / len(expense_day_values)))
        if expense_day_values
        else 0
    )
    median_expense_day_minor = (
        int(round(median(expense_day_values))) if expense_day_values else 0
    )

    return DashboardKpisRead(
        expense_total_minor=expense_total_minor,
        income_total_minor=income_total_minor,
        net_total_minor=income_total_minor - expense_total_minor,
        average_expense_day_minor=average_expense_day_minor,
        median_expense_day_minor=median_expense_day_minor,
        spending_days=len(expense_day_values),
    )


def _build_daily_spending_points(
    *,
    start: date,
    end: date,
    rollup: _ExpenseAnalyticsRollup,
    filter_groups: list[FilterGroupDefinition],
) -> list[DashboardDailySpendingPoint]:
    daily_spending: list[DashboardDailySpendingPoint] = []
    cursor = start
    while cursor < end:
        daily_spending.append(
            DashboardDailySpendingPoint(
                date=cursor,
                expense_total_minor=rollup.expense_totals_by_date.get(cursor, 0),
                filter_group_totals={
                    filter_group.key: rollup.filter_group_totals_by_date.get(cursor, {}).get(filter_group.key, 0)
                    for filter_group in filter_groups
                },
            )
        )
        cursor += timedelta(days=1)
    return daily_spending


def _build_monthly_trend(
    *,
    db: Session,
    start: date,
    end: date,
    currency_code: str,
    trend_months: int,
    account_entity_ids: set[str],
    filter_groups: list[FilterGroupDefinition],
    entry_filter: DashboardFilter | None = None,
) -> list[DashboardMonthlyTrendPoint]:
    normalized_trend_months = max(trend_months, 1)
    trend_start = _shift_month(start, -(normalized_trend_months - 1))
    trend_entries = _list_non_transfer_entries_for_window(
        db,
        start=trend_start,
        end=end,
        currency_code=currency_code,
        account_entity_ids=account_entity_ids,
        entry_filter=entry_filter,
    )

    trend_month_keys = [
        _shift_month(start, -offset).strftime("%Y-%m")
        for offset in range(normalized_trend_months - 1, -1, -1)
    ]
    monthly_rollup = {
        month_key: {
            "expense_total_minor": 0,
            "income_total_minor": 0,
            "filter_group_totals": {filter_group.key: 0 for filter_group in filter_groups},
        }
        for month_key in trend_month_keys
    }
    for entry in trend_entries:
        month_key = entry.occurred_at.strftime("%Y-%m")
        bucket = monthly_rollup.get(month_key)
        if bucket is None:
            continue
        if entry.kind == EntryKind.INCOME:
            bucket["income_total_minor"] += entry.amount_minor
            continue
        if entry.kind != EntryKind.EXPENSE:
            continue
        bucket["expense_total_minor"] += entry.amount_minor
        for key in _matching_filter_group_keys(
            entry=entry,
            filter_groups=filter_groups,
            account_entity_ids=account_entity_ids,
        ):
            bucket["filter_group_totals"][key] += entry.amount_minor

    return [
        DashboardMonthlyTrendPoint(month=month_key, **monthly_rollup[month_key])
        for month_key in trend_month_keys
    ]


def _build_weekday_spending_points(weekday_totals: dict[int, int]) -> list[DashboardWeekdaySpendingPoint]:
    return [
        DashboardWeekdaySpendingPoint(
            weekday=WEEKDAY_LABELS[index],
            total_minor=weekday_totals.get(index, 0),
        )
        for index in range(len(WEEKDAY_LABELS))
    ]


def _build_projection(
    *,
    start: date,
    end: date,
    today: date | None,
    expense_entries: list[Entry],
    expense_total_minor: int,
    filter_groups: list[FilterGroupDefinition],
    account_entity_ids: set[str],
) -> DashboardProjectionRead:
    now = today or date.today()
    is_current_month = now.year == start.year and now.month == start.month
    if is_current_month:
        as_of = min(now, end - timedelta(days=1))
        spent_to_date_minor = sum(
            entry.amount_minor for entry in expense_entries if entry.occurred_at <= as_of
        )
        spent_to_date_by_group = {filter_group.key: 0 for filter_group in filter_groups}
        for entry in expense_entries:
            if entry.occurred_at > as_of:
                continue
            for key in _matching_filter_group_keys(
                entry=entry,
                filter_groups=filter_groups,
                account_entity_ids=account_entity_ids,
            ):
                spent_to_date_by_group[key] += entry.amount_minor
        days_elapsed = max((as_of - start).days + 1, 0)
        days_in_month = (end - start).days
        days_remaining = max(days_in_month - days_elapsed, 0)
        projected_total_minor = (
            spent_to_date_minor
            if days_elapsed == 0
            else int(
                round(
                    spent_to_date_minor
                    + (spent_to_date_minor / days_elapsed) * days_remaining
                )
            )
        )
        projected_remaining_minor = max(projected_total_minor - spent_to_date_minor, 0)
        projected_filter_group_totals = {
            key: (
                amount_minor
                if days_elapsed == 0
                else int(
                    round(
                        amount_minor + (amount_minor / days_elapsed) * days_remaining
                    )
                )
            )
            for key, amount_minor in spent_to_date_by_group.items()
        }
    else:
        spent_to_date_minor = expense_total_minor
        days_elapsed = (end - start).days
        days_remaining = 0
        projected_total_minor = None
        projected_remaining_minor = None
        projected_filter_group_totals = {}

    return DashboardProjectionRead(
        is_current_month=is_current_month,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
        spent_to_date_minor=spent_to_date_minor,
        projected_total_minor=projected_total_minor,
        projected_remaining_minor=projected_remaining_minor,
        projected_filter_group_totals=projected_filter_group_totals,
    )


def _rank_expenses(
    largest_expenses: list[DashboardLargestExpenseItem],
) -> list[DashboardLargestExpenseItem]:
    return sorted(
        largest_expenses,
        key=lambda entry: (entry.amount_minor, entry.occurred_at.toordinal(), entry.name),
        reverse=True,
    )


def build_dashboard_analytics(
    db: Session,
    *,
    start: date,
    end: date,
    options: DashboardAnalyticsOptions | None = None,
    filter_groups: list[FilterGroupDefinition] | None = None,
) -> dict[str, object]:
    analytics_options = options or DashboardAnalyticsOptions()
    normalized_currency = analytics_options.currency_code.upper()
    active_filter_groups = filter_groups or []
    account_entity_ids = _account_entity_ids(
        db,
        account_filter=analytics_options.account_filter,
    )
    month_entries = _list_non_transfer_entries_for_window(
        db,
        start=start,
        end=end,
        currency_code=normalized_currency,
        account_entity_ids=account_entity_ids,
        entry_filter=analytics_options.entry_filter,
    )
    expense_entries = [entry for entry in month_entries if entry.kind == EntryKind.EXPENSE]
    rollup = _rollup_expense_entries(
        expense_entries,
        filter_groups=active_filter_groups,
        account_entity_ids=account_entity_ids,
    )

    income_total_minor = sum(entry.amount_minor for entry in month_entries if entry.kind == EntryKind.INCOME)
    kpis = _build_dashboard_kpis(
        rollup=rollup,
        income_total_minor=income_total_minor,
    )
    daily_spending = _build_daily_spending_points(
        start=start,
        end=end,
        rollup=rollup,
        filter_groups=active_filter_groups,
    )
    monthly_trend = _build_monthly_trend(
        db=db,
        start=start,
        end=end,
        currency_code=normalized_currency,
        trend_months=analytics_options.trend_months,
        account_entity_ids=account_entity_ids,
        filter_groups=active_filter_groups,
        entry_filter=analytics_options.entry_filter,
    )
    weekday_spending = _build_weekday_spending_points(rollup.weekday_totals)
    projection = _build_projection(
        start=start,
        end=end,
        today=analytics_options.today,
        expense_entries=expense_entries,
        expense_total_minor=kpis.expense_total_minor,
        filter_groups=active_filter_groups,
        account_entity_ids=account_entity_ids,
    )
    ranked_expenses = _rank_expenses(rollup.largest_expenses)

    return {
        "kpis": kpis,
        "filter_groups": [
            DashboardFilterGroupSummary(
                filter_group_id=filter_group.id,
                key=filter_group.key,
                name=filter_group.name,
                color=filter_group.color,
                total_minor=rollup.filter_group_totals.get(filter_group.key, 0),
                share=round(
                    rollup.filter_group_totals.get(filter_group.key, 0) / kpis.expense_total_minor,
                    4,
                )
                if kpis.expense_total_minor > 0
                else 0.0,
            )
            for filter_group in active_filter_groups
        ],
        "daily_spending": daily_spending,
        "monthly_trend": monthly_trend,
        "spending_by_from": _build_breakdown_items(rollup.spending_by_from),
        "spending_by_to": _build_breakdown_items(rollup.spending_by_to),
        "spending_by_tag": _build_breakdown_items(rollup.spending_by_tag),
        "weekday_spending": weekday_spending,
        "largest_expenses": ranked_expenses[:8],
        "projection": projection,
    }


__all__ = [
    "DashboardAnalyticsOptions",
    "DashboardFilter",
    "DASHBOARD_DEFAULT_CURRENCY_CODE",
    "build_dashboard_analytics",
    "build_dashboard_read",
    "build_dashboard_timeline_read",
    "list_dashboard_expense_months",
    "month_window",
]
