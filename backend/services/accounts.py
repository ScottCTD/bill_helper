from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
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

AccountPatchField = Literal["owner_user_id", "name", "markdown_body", "currency_code", "is_active"]


class AccountPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    markdown_body: str | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("Account name cannot be empty")
        return normalized

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    def includes(self, field: AccountPatchField) -> bool:
        return field in self.model_fields_set


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
    patch: AccountPatch,
) -> Account:
    if patch.includes("name") and patch.name is not None:
        if account.entity is None:
            raise ValueError("Account entity not found")
        existing_entity = find_entity_by_name(db, patch.name)
        assert_unique_name(
            existing_id=existing_entity.id if existing_entity is not None else None,
            current_id=account.id,
            conflict_detail="Entity name already exists",
        )
        rename_entity_and_sync_entry_labels(
            db,
            entity=account.entity,
            raw_name=patch.name,
        )

    if patch.includes("owner_user_id"):
        account.owner_user_id = validate_account_owner_user_id(
            db,
            owner_user_id=patch.owner_user_id,
        )
    if patch.includes("markdown_body"):
        account.markdown_body = patch.markdown_body
    if patch.includes("currency_code") and patch.currency_code is not None:
        account.currency_code = patch.currency_code
    if patch.includes("is_active") and patch.is_active is not None:
        account.is_active = patch.is_active

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
    if "owner_user_id" in update_data:
        update_data["owner_user_id"] = resolve_owner_user_id(
            db,
            owner_user_id=update_data["owner_user_id"],
            principal=principal,
        )

    try:
        patch = AccountPatch.model_validate(update_data)
        return update_account_root(
            db,
            account=account,
            patch=patch,
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
