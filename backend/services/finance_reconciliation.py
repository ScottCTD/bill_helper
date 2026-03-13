# CALLING SPEC:
# - Purpose: reconciliation queries and read-model shaping for account dashboard and agent flows.
# - Inputs: SQLAlchemy session, scoped principal filters, account rows, and date ranges.
# - Outputs: reconciliation read models and dashboard reconciliation summaries.
# - Side effects: reads database state only.

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from backend.auth.contracts import RequestPrincipal
from backend.enums_finance import EntryKind
from backend.models_finance import Account, AccountSnapshot, Entity, Entry
from backend.schemas_finance import (
    DashboardReconciliationRead,
    ReconciliationIntervalRead,
    ReconciliationRead,
    SnapshotSummaryRead,
)
from backend.services.access_scope import account_owner_filter


def _signed_entry_amount() -> ColumnElement[int]:
    return case(
        (Entry.kind == EntryKind.INCOME, Entry.amount_minor),
        else_=-Entry.amount_minor,
    )


def _snapshot_summary(snapshot: AccountSnapshot) -> SnapshotSummaryRead:
    return SnapshotSummaryRead(
        id=snapshot.id,
        snapshot_at=snapshot.snapshot_at,
        balance_minor=snapshot.balance_minor,
        note=snapshot.note,
    )


def _list_reconciliation_snapshots(
    db: Session,
    *,
    account_id: str,
    as_of: date,
) -> list[AccountSnapshot]:
    return list(
        db.scalars(
            select(AccountSnapshot)
            .where(
                AccountSnapshot.account_id == account_id,
                AccountSnapshot.snapshot_at <= as_of,
            )
            .order_by(AccountSnapshot.snapshot_at.asc(), AccountSnapshot.created_at.asc())
        )
    )


def _interval_entry_rollup(
    db: Session,
    *,
    account_id: str,
    start_exclusive: date,
    end_inclusive: date,
) -> tuple[int, int]:
    if end_inclusive < start_exclusive:
        return 0, 0

    signed_amount = _signed_entry_amount()
    account_effect = case(
        (
            and_(
                Entry.from_entity_id == account_id,
                Entry.to_entity_id == account_id,
            ),
            0,
        ),
        (Entry.from_entity_id == account_id, -Entry.amount_minor),
        (Entry.to_entity_id == account_id, Entry.amount_minor),
        (Entry.account_id == account_id, signed_amount),
        else_=None,
    )
    account_entry_filter = or_(
        Entry.from_entity_id == account_id,
        Entry.to_entity_id == account_id,
        Entry.account_id == account_id,
    )
    totals = db.execute(
        select(
            func.coalesce(func.sum(account_effect), 0),
            func.count(Entry.id),
        ).where(
            Entry.is_deleted.is_(False),
            Entry.occurred_at > start_exclusive,
            Entry.occurred_at <= end_inclusive,
            account_entry_filter,
        )
    ).one()
    return int(totals[0] or 0), int(totals[1] or 0)


def build_reconciliation(db: Session, account: Account, as_of: date) -> ReconciliationRead:
    snapshots = _list_reconciliation_snapshots(db, account_id=account.id, as_of=as_of)
    intervals: list[ReconciliationIntervalRead] = []

    for start_snapshot, end_snapshot in zip(snapshots, snapshots[1:], strict=False):
        tracked_change_minor, entry_count = _interval_entry_rollup(
            db,
            account_id=account.id,
            start_exclusive=start_snapshot.snapshot_at,
            end_inclusive=end_snapshot.snapshot_at,
        )
        bank_change_minor = end_snapshot.balance_minor - start_snapshot.balance_minor
        intervals.append(
            ReconciliationIntervalRead(
                start_snapshot=_snapshot_summary(start_snapshot),
                end_snapshot=_snapshot_summary(end_snapshot),
                is_open=False,
                tracked_change_minor=tracked_change_minor,
                bank_change_minor=bank_change_minor,
                delta_minor=tracked_change_minor - bank_change_minor,
                entry_count=entry_count,
            )
        )

    if snapshots:
        tracked_change_minor, entry_count = _interval_entry_rollup(
            db,
            account_id=account.id,
            start_exclusive=snapshots[-1].snapshot_at,
            end_inclusive=as_of,
        )
        intervals.append(
            ReconciliationIntervalRead(
                start_snapshot=_snapshot_summary(snapshots[-1]),
                end_snapshot=None,
                is_open=True,
                tracked_change_minor=tracked_change_minor,
                bank_change_minor=None,
                delta_minor=None,
                entry_count=entry_count,
            )
        )

    return ReconciliationRead(
        account_id=account.id,
        account_name=account.name,
        currency_code=account.currency_code,
        as_of=as_of,
        intervals=intervals,
    )


def build_dashboard_reconciliation_summary(
    reconciliation: ReconciliationRead,
) -> DashboardReconciliationRead:
    closed_intervals = [interval for interval in reconciliation.intervals if not interval.is_open]
    open_interval = next((interval for interval in reconciliation.intervals if interval.is_open), None)
    latest_closed = closed_intervals[-1] if closed_intervals else None
    reconciled_interval_count = sum(1 for interval in closed_intervals if interval.delta_minor == 0)
    mismatched_interval_count = sum(1 for interval in closed_intervals if interval.delta_minor != 0)
    latest_snapshot = reconciliation.intervals[-1].start_snapshot if reconciliation.intervals else None

    return DashboardReconciliationRead(
        account_id=reconciliation.account_id,
        account_name=reconciliation.account_name,
        currency_code=reconciliation.currency_code,
        latest_snapshot_at=latest_snapshot.snapshot_at if latest_snapshot else None,
        current_tracked_change_minor=open_interval.tracked_change_minor if open_interval else None,
        last_closed_delta_minor=latest_closed.delta_minor if latest_closed else None,
        mismatched_interval_count=mismatched_interval_count,
        reconciled_interval_count=reconciled_interval_count,
    )


def list_dashboard_reconciliation_accounts(
    db: Session,
    *,
    currency_code: str,
    principal: RequestPrincipal,
) -> list[Account]:
    return list(
        db.scalars(
            select(Account)
            .join(Entity, Entity.id == Account.id)
            .where(
                Account.is_active.is_(True),
                Account.currency_code == currency_code,
                account_owner_filter(principal),
            )
            .options(selectinload(Account.entity))
            .order_by(Entity.name.asc())
        )
    )


__all__ = [
    "build_dashboard_reconciliation_summary",
    "build_reconciliation",
    "list_dashboard_reconciliation_accounts",
]
