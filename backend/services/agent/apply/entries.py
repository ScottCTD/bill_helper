# CALLING SPEC:
# - Purpose: implement focused service logic for `entries`.
# - Inputs: callers that import `backend/services/agent/apply/entries.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `entries`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.models_finance import Entry
from backend.services.agent.apply.common import (
    AppliedResource,
    find_unique_entry_by_id,
    find_unique_entry_by_selector,
)
from backend.services.agent.change_contracts.entries import (
    CreateEntryPayload,
    DeleteEntryPayload,
    UpdateEntryPayload,
)
from backend.services.entries import set_entry_tags, soft_delete_entry
from backend.services.entities import ensure_entity_by_name
from backend.services.runtime_settings import resolve_runtime_settings


def apply_create_entry(
    db: Session,
    payload: CreateEntryPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    settings = resolve_runtime_settings(db)
    currency_code = (payload.currency_code or settings.default_currency_code).strip().upper()

    from_entity = ensure_entity_by_name(db, payload.from_entity, owner_user_id=principal.user_id)
    to_entity = ensure_entity_by_name(db, payload.to_entity, owner_user_id=principal.user_id)

    entry = Entry(
        account_id=None,
        kind=payload.kind,
        occurred_at=payload.date,
        name=payload.name,
        amount_minor=payload.amount_minor,
        currency_code=currency_code,
        from_entity_id=from_entity.id,
        to_entity_id=to_entity.id,
        owner_user_id=principal.user_id,
        from_entity=from_entity.name,
        to_entity=to_entity.name,
        owner=principal.user_name,
        markdown_body=payload.markdown_notes,
    )
    db.add(entry)
    set_entry_tags(db, entry, payload.tags)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_update_entry(
    db: Session,
    payload: UpdateEntryPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    if payload.entry_id is not None:
        entry = find_unique_entry_by_id(db, payload.entry_id, principal=principal)
    elif payload.selector is not None:
        entry = find_unique_entry_by_selector(db, payload.selector, principal=principal)
    else:  # pragma: no cover - validated by Pydantic
        raise ValueError("Entry reference is required")

    if "kind" in payload.patch.model_fields_set and payload.patch.kind is not None:
        entry.kind = payload.patch.kind
    if "date" in payload.patch.model_fields_set and payload.patch.date is not None:
        entry.occurred_at = payload.patch.date
    if "name" in payload.patch.model_fields_set and payload.patch.name is not None:
        entry.name = payload.patch.name
    if "amount_minor" in payload.patch.model_fields_set and payload.patch.amount_minor is not None:
        entry.amount_minor = payload.patch.amount_minor
    if "currency_code" in payload.patch.model_fields_set and payload.patch.currency_code is not None:
        entry.currency_code = payload.patch.currency_code

    if "from_entity" in payload.patch.model_fields_set:
        if payload.patch.from_entity is None:
            entry.from_entity_id = None
            entry.from_entity = None
        else:
            from_entity = ensure_entity_by_name(
                db,
                payload.patch.from_entity,
                owner_user_id=entry.owner_user_id,
            )
            entry.from_entity_id = from_entity.id
            entry.from_entity = from_entity.name

    if "to_entity" in payload.patch.model_fields_set:
        if payload.patch.to_entity is None:
            entry.to_entity_id = None
            entry.to_entity = None
        else:
            to_entity = ensure_entity_by_name(
                db,
                payload.patch.to_entity,
                owner_user_id=entry.owner_user_id,
            )
            entry.to_entity_id = to_entity.id
            entry.to_entity = to_entity.name

    if "markdown_notes" in payload.patch.model_fields_set:
        entry.markdown_body = payload.patch.markdown_notes

    if "tags" in payload.patch.model_fields_set:
        set_entry_tags(db, entry, payload.patch.tags or [])

    db.add(entry)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_delete_entry(
    db: Session,
    payload: DeleteEntryPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    if payload.entry_id is not None:
        entry = find_unique_entry_by_id(db, payload.entry_id, principal=principal)
    elif payload.selector is not None:
        entry = find_unique_entry_by_selector(db, payload.selector, principal=principal)
    else:  # pragma: no cover - validated by Pydantic
        raise ValueError("Entry reference is required")
    soft_delete_entry(db, entry)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)
