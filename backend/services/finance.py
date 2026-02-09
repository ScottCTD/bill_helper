from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from backend.enums import EntryKind
from backend.models import Account, AccountSnapshot, Entry, EntryTag, Tag
from backend.schemas import (
    DailyExpensePoint,
    DashboardBreakdownItem,
    DashboardDailySpendingPoint,
    DashboardKpisRead,
    DashboardLargestExpenseItem,
    DashboardMonthlyTrendPoint,
    DashboardProjectionRead,
    DashboardWeekdaySpendingPoint,
    ReconciliationRead,
    TagBreakdownItem,
)

DASHBOARD_DEFAULT_CURRENCY_CODE = "CAD"
DASHBOARD_DAILY_TAG_NAME = "daily"
DASHBOARD_NON_DAILY_TAG_NAMES = frozenset({"non-daily", "non_daily", "nondaily"})
WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def compute_ledger_balance(db: Session, account_id: str, as_of: date) -> int:
    signed_amount = case(
        (Entry.kind == EntryKind.INCOME, Entry.amount_minor),
        else_=-Entry.amount_minor,
    )
    total = db.scalar(
        select(func.coalesce(func.sum(signed_amount), 0)).where(
            Entry.account_id == account_id,
            Entry.is_deleted.is_(False),
            Entry.occurred_at <= as_of,
        )
    )
    return int(total or 0)


def latest_snapshot(db: Session, account_id: str, as_of: date) -> AccountSnapshot | None:
    return db.scalar(
        select(AccountSnapshot)
        .where(
            AccountSnapshot.account_id == account_id,
            AccountSnapshot.snapshot_at <= as_of,
        )
        .order_by(AccountSnapshot.snapshot_at.desc(), AccountSnapshot.created_at.desc())
        .limit(1)
    )


def build_reconciliation(db: Session, account: Account, as_of: date) -> ReconciliationRead:
    ledger_balance = compute_ledger_balance(db, account.id, as_of)
    snapshot = latest_snapshot(db, account.id, as_of)

    snapshot_balance = snapshot.balance_minor if snapshot else None
    delta = ledger_balance - snapshot_balance if snapshot_balance is not None else None

    return ReconciliationRead(
        account_id=account.id,
        account_name=account.name,
        currency_code=account.currency_code,
        as_of=as_of,
        ledger_balance_minor=ledger_balance,
        snapshot_balance_minor=snapshot_balance,
        snapshot_at=snapshot.snapshot_at if snapshot else None,
        delta_minor=delta,
    )


def month_window(month: str) -> tuple[date, date]:
    year, month_num = map(int, month.split("-"))
    start = date(year, month_num, 1)
    if month_num == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month_num + 1, 1)
    return start, end


def _shift_month(month_start: date, month_delta: int) -> date:
    normalized_month_index = (month_start.year * 12) + (month_start.month - 1) + month_delta
    year = normalized_month_index // 12
    month = (normalized_month_index % 12) + 1
    return date(year, month, 1)


def _normalize_breakdown_label(raw_label: str | None) -> str:
    normalized = (raw_label or "").strip()
    return normalized if normalized else "(unspecified)"


def _entry_has_daily_tag(entry: Entry) -> bool:
    normalized_names = {tag.name.strip().lower() for tag in entry.tags if tag.name}
    if normalized_names & DASHBOARD_NON_DAILY_TAG_NAMES:
        return False
    return DASHBOARD_DAILY_TAG_NAME in normalized_names


def _list_entries_for_window(db: Session, start: date, end: date, currency_code: str) -> list[Entry]:
    return list(
        db.scalars(
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
    )


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


def build_dashboard_analytics(
    db: Session,
    *,
    start: date,
    end: date,
    currency_code: str = DASHBOARD_DEFAULT_CURRENCY_CODE,
    trend_months: int = 6,
    today: date | None = None,
) -> dict[str, object]:
    normalized_currency = currency_code.upper()
    month_entries = _list_entries_for_window(db, start, end, normalized_currency)
    expense_entries = [entry for entry in month_entries if entry.kind == EntryKind.EXPENSE]

    expense_totals_by_date: dict[date, int] = defaultdict(int)
    daily_expense_totals_by_date: dict[date, int] = defaultdict(int)
    non_daily_expense_totals_by_date: dict[date, int] = defaultdict(int)
    spending_by_from: dict[str, int] = defaultdict(int)
    spending_by_to: dict[str, int] = defaultdict(int)
    spending_by_tag: dict[str, int] = defaultdict(int)
    weekday_totals: dict[int, int] = defaultdict(int)
    largest_expenses: list[DashboardLargestExpenseItem] = []

    income_total_minor = sum(entry.amount_minor for entry in month_entries if entry.kind == EntryKind.INCOME)

    for entry in expense_entries:
        amount_minor = entry.amount_minor
        expense_totals_by_date[entry.occurred_at] += amount_minor

        is_daily = _entry_has_daily_tag(entry)
        if is_daily:
            daily_expense_totals_by_date[entry.occurred_at] += amount_minor
        else:
            non_daily_expense_totals_by_date[entry.occurred_at] += amount_minor

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
                is_daily=is_daily,
            )
        )

    daily_expense_total_minor = sum(daily_expense_totals_by_date.values())
    non_daily_expense_total_minor = sum(non_daily_expense_totals_by_date.values())
    expense_total_minor = daily_expense_total_minor + non_daily_expense_total_minor

    daily_expense_values = list(daily_expense_totals_by_date.values())
    average_daily_expense_minor = (
        int(round(sum(daily_expense_values) / len(daily_expense_values))) if daily_expense_values else 0
    )
    median_daily_expense_minor = int(round(median(daily_expense_values))) if daily_expense_values else 0

    kpis = DashboardKpisRead(
        expense_total_minor=expense_total_minor,
        income_total_minor=income_total_minor,
        net_total_minor=income_total_minor - expense_total_minor,
        daily_expense_total_minor=daily_expense_total_minor,
        non_daily_expense_total_minor=non_daily_expense_total_minor,
        average_daily_expense_minor=average_daily_expense_minor,
        median_daily_expense_minor=median_daily_expense_minor,
        daily_spending_days=len(daily_expense_values),
    )

    daily_spending: list[DashboardDailySpendingPoint] = []
    cursor = start
    while cursor < end:
        daily_spending.append(
            DashboardDailySpendingPoint(
                date=cursor,
                expense_total_minor=expense_totals_by_date.get(cursor, 0),
                daily_expense_minor=daily_expense_totals_by_date.get(cursor, 0),
                non_daily_expense_minor=non_daily_expense_totals_by_date.get(cursor, 0),
            )
        )
        cursor += timedelta(days=1)

    trend_start = _shift_month(start, -(max(trend_months, 1) - 1))
    trend_entries = _list_entries_for_window(db, trend_start, end, normalized_currency)
    trend_month_keys = [_shift_month(start, -offset).strftime("%Y-%m") for offset in range(max(trend_months, 1) - 1, -1, -1)]
    monthly_rollup = {
        month_key: {
            "expense_total_minor": 0,
            "income_total_minor": 0,
            "daily_expense_minor": 0,
            "non_daily_expense_minor": 0,
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
        else:
            bucket["expense_total_minor"] += entry.amount_minor
            if _entry_has_daily_tag(entry):
                bucket["daily_expense_minor"] += entry.amount_minor
            else:
                bucket["non_daily_expense_minor"] += entry.amount_minor

    monthly_trend = [
        DashboardMonthlyTrendPoint(month=month_key, **monthly_rollup[month_key])
        for month_key in trend_month_keys
    ]

    weekday_spending = [
        DashboardWeekdaySpendingPoint(weekday=WEEKDAY_LABELS[index], total_minor=weekday_totals.get(index, 0))
        for index in range(len(WEEKDAY_LABELS))
    ]

    now = today or date.today()
    is_current_month = now.year == start.year and now.month == start.month
    if is_current_month:
        as_of = min(now, end - timedelta(days=1))
        spent_to_date_minor = sum(
            entry.amount_minor for entry in expense_entries if entry.occurred_at <= as_of
        )
        days_elapsed = max((as_of - start).days + 1, 0)
        days_in_month = (end - start).days
        days_remaining = max(days_in_month - days_elapsed, 0)
        projected_total_minor = (
            spent_to_date_minor
            if days_elapsed == 0
            else int(round(spent_to_date_minor + (spent_to_date_minor / days_elapsed) * days_remaining))
        )
        projected_remaining_minor = max(projected_total_minor - spent_to_date_minor, 0)
    else:
        spent_to_date_minor = expense_total_minor
        days_elapsed = (end - start).days
        days_remaining = 0
        projected_total_minor = None
        projected_remaining_minor = None

    projection = DashboardProjectionRead(
        is_current_month=is_current_month,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
        spent_to_date_minor=spent_to_date_minor,
        projected_total_minor=projected_total_minor,
        projected_remaining_minor=projected_remaining_minor,
    )

    ranked_expenses = sorted(
        largest_expenses,
        key=lambda entry: (entry.amount_minor, entry.occurred_at.toordinal(), entry.name),
        reverse=True,
    )

    return {
        "kpis": kpis,
        "daily_spending": daily_spending,
        "monthly_trend": monthly_trend,
        "spending_by_from": _build_breakdown_items(spending_by_from),
        "spending_by_to": _build_breakdown_items(spending_by_to),
        "spending_by_tag": _build_breakdown_items(spending_by_tag),
        "weekday_spending": weekday_spending,
        "largest_expenses": ranked_expenses[:8],
        "projection": projection,
    }


def aggregate_monthly_totals(db: Session, start: date, end: date) -> tuple[dict[str, int], dict[str, int]]:
    rows = db.execute(
        select(
            Entry.kind,
            Entry.currency_code,
            func.coalesce(func.sum(Entry.amount_minor), 0),
        ).where(
            Entry.is_deleted.is_(False),
            Entry.occurred_at >= start,
            Entry.occurred_at < end,
        ).group_by(Entry.kind, Entry.currency_code)
    ).all()

    expenses: dict[str, int] = defaultdict(int)
    incomes: dict[str, int] = defaultdict(int)
    for kind, currency_code, total in rows:
        if kind == EntryKind.EXPENSE:
            expenses[currency_code] += int(total or 0)
        else:
            incomes[currency_code] += int(total or 0)
    return dict(expenses), dict(incomes)


def aggregate_daily_expenses(db: Session, start: date, end: date) -> list[DailyExpensePoint]:
    rows = db.execute(
        select(
            Entry.occurred_at,
            Entry.currency_code,
            func.coalesce(func.sum(Entry.amount_minor), 0),
        )
        .where(
            Entry.is_deleted.is_(False),
            Entry.kind == EntryKind.EXPENSE,
            Entry.occurred_at >= start,
            Entry.occurred_at < end,
        )
        .group_by(Entry.occurred_at, Entry.currency_code)
        .order_by(Entry.occurred_at.asc())
    ).all()

    return [
        DailyExpensePoint(date=occurred_at, currency_code=currency_code, total_minor=int(total or 0))
        for occurred_at, currency_code, total in rows
    ]


def aggregate_top_tags(db: Session, start: date, end: date, limit: int = 10) -> list[TagBreakdownItem]:
    rows = db.execute(
        select(
            Tag.name,
            Entry.currency_code,
            func.coalesce(func.sum(Entry.amount_minor), 0).label("total_minor"),
        )
        .join(EntryTag, EntryTag.tag_id == Tag.id)
        .join(Entry, Entry.id == EntryTag.entry_id)
        .where(
            Entry.is_deleted.is_(False),
            Entry.kind == EntryKind.EXPENSE,
            Entry.occurred_at >= start,
            Entry.occurred_at < end,
        )
        .group_by(Tag.name, Entry.currency_code)
        .order_by(func.sum(Entry.amount_minor).desc())
        .limit(limit)
    ).all()

    return [
        TagBreakdownItem(tag=tag_name, currency_code=currency_code, total_minor=int(total_minor or 0))
        for tag_name, currency_code, total_minor in rows
    ]
