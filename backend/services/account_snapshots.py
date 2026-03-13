# CALLING SPEC:
# - Purpose: implement focused service logic for `account_snapshots`.
# - Inputs: callers that import `backend/services/account_snapshots.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `account_snapshots`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models_finance import Account, AccountSnapshot
from backend.services.crud_policy import PolicyViolation


def create_account_snapshot(
    db: Session,
    *,
    account: Account,
    snapshot_at: date,
    balance_minor: int,
    note: str | None,
) -> AccountSnapshot:
    snapshot = AccountSnapshot(
        account_id=account.id,
        snapshot_at=snapshot_at,
        balance_minor=balance_minor,
        note=note,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def list_account_snapshots(
    db: Session,
    *,
    account_id: str,
) -> list[AccountSnapshot]:
    return list(
        db.scalars(
            select(AccountSnapshot)
            .where(AccountSnapshot.account_id == account_id)
            .order_by(AccountSnapshot.snapshot_at.desc(), AccountSnapshot.created_at.desc())
        )
    )


def get_account_snapshot(
    db: Session,
    *,
    account_id: str,
    snapshot_id: str,
) -> AccountSnapshot | None:
    return db.scalar(
        select(AccountSnapshot).where(
            AccountSnapshot.id == snapshot_id,
            AccountSnapshot.account_id == account_id,
        )
    )


def delete_account_snapshot(
    db: Session,
    *,
    account: Account,
    snapshot_id: str,
) -> None:
    snapshot = get_account_snapshot(db, account_id=account.id, snapshot_id=snapshot_id)
    if snapshot is None:
        raise PolicyViolation.not_found("Snapshot not found")
    db.delete(snapshot)
    db.flush()
