from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from backend.auth import RequestPrincipal
from backend.models_finance import Account, Entity, Entry, User
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


_UNSET = object()


def validate_account_owner_user_id(
    db: Session,
    *,
    owner_user_id: str | None,
) -> str | None:
    if owner_user_id is None:
        return None
    user = db.get(User, owner_user_id)
    if user is None:
        raise ValueError("Owner user not found")
    return owner_user_id


def resolve_owner_user_id(
    db: Session,
    *,
    owner_user_id: str | None,
    principal: RequestPrincipal,
) -> str | None:
    if owner_user_id is not None:
        try:
            validated_owner_user_id = validate_account_owner_user_id(db, owner_user_id=owner_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        ensure_principal_can_assign_user(principal, user_id=validated_owner_user_id)
        return validated_owner_user_id
    return principal.user_id


def find_account_by_name(db: Session, name: str) -> Account | None:
    normalized_name = normalize_entity_name(name)
    if not normalized_name:
        return None
    return db.scalar(
        select(Account)
        .join(Entity, Entity.id == Account.id)
        .options(selectinload(Account.entity))
        .where(func.lower(Entity.name) == normalized_name.lower())
    )


def create_account_root(
    db: Session,
    *,
    name: str,
    owner_user_id: str | None,
    markdown_body: str | None,
    currency_code: str,
    is_active: bool,
) -> Account:
    normalized_name = normalize_entity_name(name)
    if not normalized_name:
        raise ValueError("Account name cannot be empty")

    validated_owner_user_id = validate_account_owner_user_id(db, owner_user_id=owner_user_id)
    existing_entity = find_entity_by_name(db, normalized_name)
    if existing_entity is not None:
        raise ValueError("Entity name already exists")

    entity = Entity(name=normalized_name, category=None)
    db.add(entity)
    db.flush()

    account = Account(
        id=entity.id,
        owner_user_id=validated_owner_user_id,
        markdown_body=markdown_body,
        currency_code=currency_code.upper(),
        is_active=is_active,
    )
    db.add(account)
    db.flush()
    db.refresh(account, attribute_names=["entity"])
    return account


def update_account_root(
    db: Session,
    *,
    account: Account,
    name: str | None | object = _UNSET,
    owner_user_id: str | None | object = _UNSET,
    markdown_body: str | None | object = _UNSET,
    currency_code: str | None | object = _UNSET,
    is_active: bool | None | object = _UNSET,
) -> Account:
    if name is not _UNSET and name is not None:
        if account.entity is None:
            raise ValueError("Account entity not found")
        target_name = normalize_entity_name(name)
        if not target_name:
            raise ValueError("Account name cannot be empty")
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

    if owner_user_id is not _UNSET:
        next_owner_user_id = owner_user_id if isinstance(owner_user_id, str) else None
        account.owner_user_id = validate_account_owner_user_id(
            db,
            owner_user_id=next_owner_user_id,
        )
    if markdown_body is not _UNSET:
        account.markdown_body = markdown_body if isinstance(markdown_body, str) or markdown_body is None else account.markdown_body
    if currency_code is not _UNSET and currency_code is not None:
        account.currency_code = currency_code.upper()
    if is_active is not _UNSET and isinstance(is_active, bool):
        account.is_active = is_active

    db.add(account)
    db.flush()
    return account


def create_account_from_payload(
    db: Session,
    *,
    payload: AccountCreate,
    principal: RequestPrincipal,
) -> Account:
    try:
        return create_account_root(
            db,
            name=payload.name,
            owner_user_id=resolve_owner_user_id(
                db,
                owner_user_id=payload.owner_user_id,
                principal=principal,
            ),
            markdown_body=payload.markdown_body,
            currency_code=payload.currency_code,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_409_CONFLICT
        if detail == "Account name cannot be empty":
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc


def update_account_from_payload(
    db: Session,
    *,
    account: Account,
    payload: AccountUpdate,
    principal: RequestPrincipal,
) -> Account:
    update_data = payload.model_dump(exclude_unset=True)
    owner_user_id: str | None | object = _UNSET
    if "owner_user_id" in update_data:
        owner_user_id = resolve_owner_user_id(
            db,
            owner_user_id=update_data["owner_user_id"],
            principal=principal,
        )

    try:
        return update_account_root(
            db,
            account=account,
            name=update_data.get("name", _UNSET),
            owner_user_id=owner_user_id,
            markdown_body=update_data.get("markdown_body", _UNSET),
            currency_code=update_data.get("currency_code", _UNSET),
            is_active=update_data.get("is_active", _UNSET),
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_409_CONFLICT
        if detail == "Account name cannot be empty":
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc


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
