from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.models_finance import Account
from backend.services.account_snapshots import create_account_snapshot, delete_account_snapshot
from backend.services.accounts import (
    create_account,
    delete_account_and_entity_root,
    find_account_by_name,
    update_account,
)
from backend.services.agent.apply.common import AppliedResource
from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload,
    CreateEntityPayload,
    CreateTagPayload,
    DeleteAccountPayload,
    DeleteEntityPayload,
    DeleteTagPayload,
    SnapshotCreatePayload,
    SnapshotDeletePayload,
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
from backend.services.tags import create_tag, delete_tag, find_tag_by_name, update_tag


def apply_create_tag(db: Session, payload: CreateTagPayload, principal: RequestPrincipal) -> AppliedResource:
    existing = find_tag_by_name(db, payload.name, owner_user_id=principal.user_id)
    if existing is not None:
        return AppliedResource(resource_type="tag", resource_id=str(existing.id))

    try:
        tag = create_tag(
            db,
            command=TagCreateCommand(name=payload.name, color=None, description=None, type=payload.type),
            owner_user_id=principal.user_id,
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_update_tag(db: Session, payload: UpdateTagPayload, principal: RequestPrincipal) -> AppliedResource:
    tag = find_tag_by_name(db, payload.name, owner_user_id=principal.user_id)
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


def apply_delete_tag(db: Session, payload: DeleteTagPayload, principal: RequestPrincipal) -> AppliedResource:
    tag = find_tag_by_name(db, payload.name, owner_user_id=principal.user_id)
    if tag is None:
        raise ValueError("Tag not found")

    resource_id = str(tag.id)
    delete_tag(db, tag=tag)
    return AppliedResource(resource_type="tag", resource_id=resource_id)


def apply_create_entity(
    db: Session,
    payload: CreateEntityPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    try:
        entity = create_entity(
            db,
            command=EntityCreateCommand(name=payload.name, category=payload.category),
            principal=principal,
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_update_entity(
    db: Session,
    payload: UpdateEntityPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    entity = find_entity_by_name(db, payload.name, owner_user_id=principal.user_id)
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


def apply_delete_entity(
    db: Session,
    payload: DeleteEntityPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    entity = find_entity_by_name(db, payload.name, owner_user_id=principal.user_id)
    if entity is None:
        raise ValueError("Entity not found")

    resource_id = entity.id
    try:
        delete_entity_and_preserve_labels(db, entity=entity)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=resource_id)


def apply_create_account(
    db: Session,
    payload: CreateAccountPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    command = AccountCreateCommand(
        name=payload.name,
        owner_user_id=principal.user_id,
        markdown_body=payload.markdown_body,
        currency_code=payload.currency_code,
        is_active=payload.is_active,
    )
    try:
        account = create_account(
            db,
            command=command,
            principal=principal,
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="account", resource_id=account.id)


def apply_update_account(
    db: Session,
    payload: UpdateAccountPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    account = find_account_by_name(db, payload.name, owner_user_id=principal.user_id)
    if account is None:
        raise ValueError("Account not found")

    patch = AccountPatch.model_validate(payload.patch.model_dump(exclude_unset=True))
    try:
        update_account(db, account=account, patch=patch, principal=principal)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="account", resource_id=account.id)


def apply_delete_account(
    db: Session,
    payload: DeleteAccountPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    account = find_account_by_name(db, payload.name, owner_user_id=principal.user_id)
    if account is None:
        raise ValueError("Account not found")

    resource_id = account.id
    delete_account_and_entity_root(db, account=account)
    return AppliedResource(resource_type="account", resource_id=resource_id)


def apply_create_snapshot(
    db: Session,
    payload: SnapshotCreatePayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    account = db.scalar(
        select(Account).where(
            Account.id == payload.account_id,
            Account.owner_user_id == principal.user_id,
        )
    )
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


def apply_delete_snapshot(
    db: Session,
    payload: SnapshotDeletePayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    account = db.scalar(
        select(Account).where(
            Account.id == payload.account_id,
            Account.owner_user_id == principal.user_id,
        )
    )
    if account is None:
        raise ValueError("Account not found")

    delete_account_snapshot(db, account=account, snapshot_id=payload.snapshot_id)
    return AppliedResource(resource_type="snapshot", resource_id=payload.snapshot_id)
