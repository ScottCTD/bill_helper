from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal
from backend.models_finance import Account, Entity, User
from backend.schemas_finance import AccountCreate, AccountUpdate
from backend.services.access_scope import ensure_principal_can_assign_user
from backend.services.entities import (
    ensure_entity_by_name,
    find_entity_by_name,
    normalize_entity_name,
    read_entity_category,
    set_entity_category,
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


def resolve_account_entity_id(
    db: Session,
    *,
    account_name: str,
    existing_entity_id: str | None = None,
) -> str:
    normalized_name = normalize_entity_name(account_name)
    if not normalized_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account name cannot be empty")

    existing_by_name = find_entity_by_name(db, normalized_name)
    existing_by_name_category = read_entity_category(db, existing_by_name) if existing_by_name is not None else None
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
            entity = ensure_entity_by_name(db, normalized_name, category="account")
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

    return ensure_entity_by_name(db, normalized_name, category="account").id


def create_account_from_payload(
    db: Session,
    *,
    payload: AccountCreate,
    principal: RequestPrincipal,
) -> Account:
    normalized_name = normalize_entity_name(payload.name)
    account = Account(
        owner_user_id=resolve_owner_user_id(
            db,
            owner_user_id=payload.owner_user_id,
            principal=principal,
        ),
        entity_id=resolve_account_entity_id(db, account_name=normalized_name),
        name=normalized_name,
        markdown_body=payload.markdown_body,
        currency_code=payload.currency_code.upper(),
        is_active=payload.is_active,
    )
    db.add(account)
    db.flush()
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
        normalized_name = normalize_entity_name(update_data["name"])
        update_data["name"] = normalized_name
        account.entity_id = resolve_account_entity_id(
            db,
            account_name=normalized_name,
            existing_entity_id=account.entity_id,
        )

    for field, value in update_data.items():
        setattr(account, field, value)

    db.add(account)
    db.flush()
    return account
