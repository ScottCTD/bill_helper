from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models_finance import Account, Tag
from backend.services.account_snapshots import create_account_snapshot, delete_account_snapshot
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
    SnapshotCreatePayload,
    SnapshotDeletePayload,
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


def apply_create_tag(db: Session, payload: CreateTagPayload, actor_name: str) -> AppliedResource:
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


def apply_update_tag(db: Session, payload: UpdateTagPayload, actor_name: str) -> AppliedResource:
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


def apply_delete_tag(db: Session, payload: DeleteTagPayload, actor_name: str) -> AppliedResource:
    tag = db.scalar(select(Tag).where(Tag.name == payload.name))
    if tag is None:
        raise ValueError("Tag not found")

    resource_id = str(tag.id)
    delete_tag(db, tag=tag)
    return AppliedResource(resource_type="tag", resource_id=resource_id)


def apply_create_entity(db: Session, payload: CreateEntityPayload, actor_name: str) -> AppliedResource:
    try:
        entity = create_entity(
            db,
            command=EntityCreateCommand(name=payload.name, category=payload.category),
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_update_entity(db: Session, payload: UpdateEntityPayload, actor_name: str) -> AppliedResource:
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


def apply_delete_entity(db: Session, payload: DeleteEntityPayload, actor_name: str) -> AppliedResource:
    entity = find_entity_by_name(db, payload.name)
    if entity is None:
        raise ValueError("Entity not found")

    resource_id = entity.id
    try:
        delete_entity_and_preserve_labels(db, entity=entity)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=resource_id)


def apply_create_account(db: Session, payload: CreateAccountPayload, actor_name: str) -> AppliedResource:
    owner_user = resolve_current_user(db, actor_name=actor_name)
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


def apply_update_account(db: Session, payload: UpdateAccountPayload, actor_name: str) -> AppliedResource:
    account = find_account_by_name(db, payload.name)
    if account is None:
        raise ValueError("Account not found")

    patch = AccountPatch.model_validate(payload.patch.model_dump(exclude_unset=True))
    try:
        update_account_root(db, account=account, patch=patch)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="account", resource_id=account.id)


def apply_delete_account(db: Session, payload: DeleteAccountPayload, actor_name: str) -> AppliedResource:
    account = find_account_by_name(db, payload.name)
    if account is None:
        raise ValueError("Account not found")

    resource_id = account.id
    delete_account_and_entity_root(db, account=account)
    return AppliedResource(resource_type="account", resource_id=resource_id)


def apply_create_snapshot(db: Session, payload: SnapshotCreatePayload, actor_name: str) -> AppliedResource:
    account = db.scalar(select(Account).where(Account.id == payload.account_id))
    if account is None:
        raise ValueError("Account not found")

    snapshot = create_account_snapshot(
        db,
        account=account,
        snapshot_at=payload.snapshot_at,
        balance_minor=payload.balance_minor,
        note=payload.note,
    )
    return AppliedResource(resource_type="snapshot", resource_id=snapshot.id)


def apply_delete_snapshot(db: Session, payload: SnapshotDeletePayload, actor_name: str) -> AppliedResource:
    account = db.scalar(select(Account).where(Account.id == payload.account_id))
    if account is None:
        raise ValueError("Account not found")

    delete_account_snapshot(db, account=account, snapshot_id=payload.snapshot_id)
    return AppliedResource(resource_type="snapshot", resource_id=payload.snapshot_id)
