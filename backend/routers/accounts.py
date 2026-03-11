from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal
from backend.database import get_db
from backend.models_finance import Account, Entity
from backend.schemas_finance import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    ReconciliationRead,
    SnapshotCreate,
    SnapshotRead,
)
from backend.services.access_scope import (
    account_owner_filter,
    get_account_for_principal_or_404,
)
from backend.services.accounts import (
    create_account as create_account_service,
    delete_account_and_entity_root,
    update_account as update_account_service,
)
from backend.services.account_snapshots import (
    create_account_snapshot,
    delete_account_snapshot,
    list_account_snapshots,
)
from backend.services.finance_contracts import AccountCreateCommand, AccountPatch
from backend.services.finance import build_reconciliation

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> AccountRead:
    account = create_account_service(
        db,
        command=AccountCreateCommand.model_validate(payload.model_dump()),
        principal=principal,
    )
    db.commit()
    db.refresh(account)
    db.refresh(account, attribute_names=["entity"])
    return AccountRead.model_validate(account)


@router.get("", response_model=list[AccountRead])
def list_accounts(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> list[AccountRead]:
    accounts = list(
        db.scalars(
            select(Account)
            .join(Entity, Entity.id == Account.id)
            .where(account_owner_filter(principal))
            .options(selectinload(Account.entity))
            .order_by(Entity.name.asc(), Account.created_at.asc())
        )
    )
    return [AccountRead.model_validate(account) for account in accounts]


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: str,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> AccountRead:
    account = get_account_for_principal_or_404(db, account_id=account_id, principal=principal)
    update_account_service(
        db,
        account=account,
        patch=AccountPatch.model_validate(payload.model_dump(exclude_unset=True)),
        principal=principal,
    )
    db.commit()
    db.refresh(account)
    db.refresh(account, attribute_names=["entity"])
    return AccountRead.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> None:
    account = get_account_for_principal_or_404(db, account_id=account_id, principal=principal)
    delete_account_and_entity_root(db, account=account)
    db.commit()


@router.post("/{account_id}/snapshots", response_model=SnapshotRead, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    account_id: str,
    payload: SnapshotCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> SnapshotRead:
    account = get_account_for_principal_or_404(db, account_id=account_id, principal=principal)

    snapshot = create_account_snapshot(
        db,
        account=account,
        snapshot_at=payload.snapshot_at,
        balance_minor=payload.balance_minor,
        note=payload.note,
    )
    db.commit()
    db.refresh(snapshot)
    return SnapshotRead.model_validate(snapshot)


@router.get("/{account_id}/snapshots", response_model=list[SnapshotRead])
def list_snapshots(
    account_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> list[SnapshotRead]:
    get_account_for_principal_or_404(db, account_id=account_id, principal=principal)

    snapshots = list_account_snapshots(db, account_id=account_id)
    return [SnapshotRead.model_validate(snapshot) for snapshot in snapshots]


@router.delete("/{account_id}/snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snapshot(
    account_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> None:
    account = get_account_for_principal_or_404(db, account_id=account_id, principal=principal)
    delete_account_snapshot(db, account=account, snapshot_id=snapshot_id)
    db.commit()


@router.get("/{account_id}/reconciliation", response_model=ReconciliationRead)
def account_reconciliation(
    account_id: str,
    as_of: date | None = None,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> ReconciliationRead:
    account = get_account_for_principal_or_404(db, account_id=account_id, principal=principal)

    effective_as_of = as_of or date.today()
    return build_reconciliation(db, account, effective_as_of)
