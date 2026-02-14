from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account, AccountSnapshot, Entity, User
from backend.schemas import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    ReconciliationRead,
    SnapshotCreate,
    SnapshotRead,
)
from backend.services.entities import (
    find_entity_by_name,
    get_entity_category,
    get_or_create_entity,
    normalize_entity_name,
    set_entity_category,
)
from backend.services.finance import build_reconciliation
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.users import ensure_current_user

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _resolve_owner_user_id(db: Session, owner_user_id: str | None) -> str | None:
    if owner_user_id is not None:
        if db.get(User, owner_user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner user not found")
        return owner_user_id

    settings = resolve_runtime_settings(db)
    owner_user = ensure_current_user(db, settings.current_user_name)
    return owner_user.id


def _resolve_account_entity_id(db: Session, account_name: str, existing_entity_id: str | None = None) -> str:
    normalized_name = normalize_entity_name(account_name)
    if not normalized_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account name cannot be empty")

    existing_by_name = find_entity_by_name(db, normalized_name)
    existing_by_name_category = get_entity_category(db, existing_by_name) if existing_by_name is not None else None
    if existing_entity_id is not None:
        entity = db.get(Entity, existing_entity_id)
        if entity is None and existing_by_name is not None:
            if existing_by_name_category not in (None, "account"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Entity name already used by a non-account entity",
                )
            entity = existing_by_name
        if entity is None:
            entity = get_or_create_entity(db, normalized_name, category="account")
            return entity.id

        if existing_by_name is not None and existing_by_name.id != entity.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entity name already exists")

        entity.name = normalized_name
        set_entity_category(db, entity, "account")
        return entity.id

    if existing_by_name is not None:
        if existing_by_name_category not in (None, "account"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Entity name already used by a non-account entity",
            )
        if existing_by_name_category is None:
            set_entity_category(db, existing_by_name, "account")
        return existing_by_name.id

    return get_or_create_entity(db, normalized_name, category="account").id


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> AccountRead:
    normalized_name = normalize_entity_name(payload.name)
    account = Account(
        owner_user_id=_resolve_owner_user_id(db, payload.owner_user_id),
        entity_id=_resolve_account_entity_id(db, normalized_name),
        name=normalized_name,
        institution=payload.institution,
        account_type=payload.account_type,
        currency_code=payload.currency_code.upper(),
        is_active=payload.is_active,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return AccountRead.model_validate(account)


@router.get("", response_model=list[AccountRead])
def list_accounts(db: Session = Depends(get_db)) -> list[AccountRead]:
    accounts = list(db.scalars(select(Account).order_by(Account.created_at.asc())))
    return [AccountRead.model_validate(account) for account in accounts]


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(account_id: str, payload: AccountUpdate, db: Session = Depends(get_db)) -> AccountRead:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "currency_code" in update_data and update_data["currency_code"] is not None:
        update_data["currency_code"] = update_data["currency_code"].upper()
    if "owner_user_id" in update_data:
        update_data["owner_user_id"] = _resolve_owner_user_id(db, update_data["owner_user_id"])
    if "name" in update_data and update_data["name"] is not None:
        normalized_name = normalize_entity_name(update_data["name"])
        update_data["name"] = normalized_name
        account.entity_id = _resolve_account_entity_id(db, normalized_name, existing_entity_id=account.entity_id)

    for field, value in update_data.items():
        setattr(account, field, value)

    db.add(account)
    db.commit()
    db.refresh(account)
    return AccountRead.model_validate(account)


@router.post("/{account_id}/snapshots", response_model=SnapshotRead, status_code=status.HTTP_201_CREATED)
def create_snapshot(account_id: str, payload: SnapshotCreate, db: Session = Depends(get_db)) -> SnapshotRead:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    snapshot = AccountSnapshot(
        account_id=account_id,
        snapshot_at=payload.snapshot_at,
        balance_minor=payload.balance_minor,
        note=payload.note,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return SnapshotRead.model_validate(snapshot)


@router.get("/{account_id}/snapshots", response_model=list[SnapshotRead])
def list_snapshots(account_id: str, db: Session = Depends(get_db)) -> list[SnapshotRead]:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    snapshots = list(
        db.scalars(
            select(AccountSnapshot)
            .where(AccountSnapshot.account_id == account_id)
            .order_by(AccountSnapshot.snapshot_at.desc(), AccountSnapshot.created_at.desc())
        )
    )
    return [SnapshotRead.model_validate(snapshot) for snapshot in snapshots]


@router.get("/{account_id}/reconciliation", response_model=ReconciliationRead)
def account_reconciliation(account_id: str, as_of: date | None = None, db: Session = Depends(get_db)) -> ReconciliationRead:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    effective_as_of = as_of or date.today()
    return build_reconciliation(db, account, effective_as_of)
