from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal
from backend.models_finance import Account, Entity, User, Entry
from backend.schemas_finance import AccountCreate, AccountUpdate
from backend.services.access_scope import ensure_principal_can_assign_user
from backend.services.crud_policy import assert_unique_name
from backend.services.entities import (
    clear_entity_category,
    detach_entity_references_preserve_labels,
    find_entity_by_name,
    normalize_entity_name,
    rename_entity_and_sync_entry_labels,
)


def resolve_owner_user_id(
    db: Session,
    *,
    owner_user_id: str | None,
    principal: RequestPrincipal,
) -> str | None:
    if owner_user_id is not None:
        user = db.get(User, owner_user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner user not found")
        ensure_principal_can_assign_user(principal, user_id=user.id)
        return owner_user_id
    return principal.user_id


def create_account_from_payload(
    db: Session,
    *,
    payload: AccountCreate,
    principal: RequestPrincipal,
) -> Account:
    normalized_name = normalize_entity_name(payload.name)
    if not normalized_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account name cannot be empty")

    existing_entity = find_entity_by_name(db, normalized_name)
    if existing_entity is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entity name already exists")

    entity = Entity(name=normalized_name, category=None)
    db.add(entity)
    db.flush()

    account = Account(
        id=entity.id,
        owner_user_id=resolve_owner_user_id(
            db,
            owner_user_id=payload.owner_user_id,
            principal=principal,
        ),
        markdown_body=payload.markdown_body,
        currency_code=payload.currency_code.upper(),
        is_active=payload.is_active,
    )
    db.add(account)
    db.flush()
    db.refresh(account, attribute_names=["entity"])
    return account


def update_account_from_payload(
    db: Session,
    *,
    account: Account,
    payload: AccountUpdate,
    principal: RequestPrincipal,
) -> Account:
    update_data = payload.model_dump(exclude_unset=True)
    if "currency_code" in update_data and update_data["currency_code"] is not None:
        update_data["currency_code"] = update_data["currency_code"].upper()
    if "owner_user_id" in update_data:
        update_data["owner_user_id"] = resolve_owner_user_id(
            db,
            owner_user_id=update_data["owner_user_id"],
            principal=principal,
        )
    if "name" in update_data and update_data["name"] is not None:
        if account.entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account entity not found")
        target_name = normalize_entity_name(update_data.pop("name"))
        if not target_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account name cannot be empty")
        existing_entity = find_entity_by_name(db, target_name)
        assert_unique_name(
            existing_id=existing_entity.id if existing_entity is not None else None,
            current_id=account.id,
            conflict_detail="Entity name already exists",
        )
        rename_entity_and_sync_entry_labels(
            db,
            entity=account.entity,
            raw_name=target_name,
        )

    for field, value in update_data.items():
        setattr(account, field, value)

    db.add(account)
    db.flush()
    return account


def delete_account_and_entity_root(db: Session, *, account: Account) -> None:
    if account.entity is None:
        raise ValueError("Account entity not found")

    db.execute(
        update(Entry)
        .where(Entry.account_id == account.id)
        .values(account_id=None)
    )
    detach_entity_references_preserve_labels(db, entity=account.entity)
    clear_entity_category(db, account.entity)
    db.delete(account)
    db.delete(account.entity)
    db.flush()
