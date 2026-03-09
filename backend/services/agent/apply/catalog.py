from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models_finance import Tag
from backend.services.accounts import (
    create_account_root,
    delete_account_and_entity_root,
    find_account_by_name,
    update_account_root,
)
from backend.services.agent.apply.common import AppliedResource, resolve_current_user
from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload,
    CreateEntityPayload,
    CreateTagPayload,
    DeleteAccountPayload,
    DeleteEntityPayload,
    DeleteTagPayload,
    UpdateAccountPayload,
    UpdateEntityPayload,
    UpdateTagPayload,
)
from backend.services.crud_policy import PolicyViolation
from backend.services.entities import (
    create_entity,
    delete_entity_and_preserve_labels,
    find_entity_by_name,
    update_entity,
)
from backend.services.finance_contracts import (
    AccountCreateCommand,
    AccountPatch,
    EntityCreateCommand,
    EntityPatch,
    TagCreateCommand,
    TagPatch,
)
from backend.services.tags import create_tag, delete_tag, update_tag


def apply_create_tag(db: Session, payload: CreateTagPayload) -> AppliedResource:
    existing = db.scalar(select(Tag).where(Tag.name == payload.name))
    if existing is not None:
        return AppliedResource(resource_type="tag", resource_id=str(existing.id))

    try:
        tag = create_tag(
            db,
            command=TagCreateCommand(name=payload.name, color=None, description=None, type=payload.type),
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_update_tag(db: Session, payload: UpdateTagPayload) -> AppliedResource:
    tag = db.scalar(select(Tag).where(Tag.name == payload.name))
    if tag is None:
        raise ValueError("Tag not found")

    try:
        update_tag(
            db,
            tag=tag,
            patch=TagPatch.model_validate(payload.patch.model_dump(exclude_unset=True)),
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_delete_tag(db: Session, payload: DeleteTagPayload) -> AppliedResource:
    tag = db.scalar(select(Tag).where(Tag.name == payload.name))
    if tag is None:
        raise ValueError("Tag not found")

    resource_id = str(tag.id)
    delete_tag(db, tag=tag)
    return AppliedResource(resource_type="tag", resource_id=resource_id)


def apply_create_entity(db: Session, payload: CreateEntityPayload) -> AppliedResource:
    try:
        entity = create_entity(
            db,
            command=EntityCreateCommand(name=payload.name, category=payload.category),
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_update_entity(db: Session, payload: UpdateEntityPayload) -> AppliedResource:
    entity = find_entity_by_name(db, payload.name)
    if entity is None:
        raise ValueError("Entity not found")
    try:
        update_entity(
            db,
            entity=entity,
            patch=EntityPatch.model_validate(payload.patch.model_dump(exclude_unset=True)),
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_delete_entity(db: Session, payload: DeleteEntityPayload) -> AppliedResource:
    entity = find_entity_by_name(db, payload.name)
    if entity is None:
        raise ValueError("Entity not found")

    resource_id = entity.id
    try:
        delete_entity_and_preserve_labels(db, entity=entity)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=resource_id)


def apply_create_account(db: Session, payload: CreateAccountPayload) -> AppliedResource:
    owner_user = resolve_current_user(db)
    command = AccountCreateCommand(
        name=payload.name,
        owner_user_id=owner_user.id,
        markdown_body=payload.markdown_body,
        currency_code=payload.currency_code,
        is_active=payload.is_active,
    )
    try:
        account = create_account_root(
            db,
            name=command.name,
            owner_user_id=command.owner_user_id,
            markdown_body=command.markdown_body,
            currency_code=command.currency_code,
            is_active=command.is_active,
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="account", resource_id=account.id)


def apply_update_account(db: Session, payload: UpdateAccountPayload) -> AppliedResource:
    account = find_account_by_name(db, payload.name)
    if account is None:
        raise ValueError("Account not found")

    patch = AccountPatch.model_validate(payload.patch.model_dump(exclude_unset=True))
    try:
        update_account_root(db, account=account, patch=patch)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="account", resource_id=account.id)


def apply_delete_account(db: Session, payload: DeleteAccountPayload) -> AppliedResource:
    account = find_account_by_name(db, payload.name)
    if account is None:
        raise ValueError("Account not found")

    resource_id = account.id
    delete_account_and_entity_root(db, account=account)
    return AppliedResource(resource_type="account", resource_id=resource_id)
