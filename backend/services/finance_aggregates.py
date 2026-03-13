# CALLING SPEC:
# - Purpose: legacy aggregate reports for monthly totals, daily expenses, and top tags.
# - Inputs: SQLAlchemy session and date ranges.
# - Outputs: aggregate dictionaries and read-model lists used by reporting callers.
# - Side effects: reads database state only.

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.enums_finance import EntryKind
from backend.models_finance import Entry, EntryTag, Tag
from backend.schemas_finance import DailyExpensePoint, TagBreakdownItem


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


__all__ = [
    "aggregate_daily_expenses",
    "aggregate_monthly_totals",
    "aggregate_top_tags",
]
