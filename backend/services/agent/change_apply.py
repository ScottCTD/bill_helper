from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.enums import AgentChangeType
from backend.models import Account, Entity, Entry, Tag, User
from backend.schemas import EntryCreate
from backend.services.entries import normalize_tag_name, set_entry_tags
from backend.services.entities import get_or_create_entity, normalize_entity_name
from backend.services.groups import assign_initial_group
from backend.services.tags import resolve_tag_color
from backend.services.users import ensure_current_user, get_or_create_user, normalize_user_name


@dataclass(frozen=True, slots=True)
class AppliedResource:
    resource_type: str
    resource_id: str


ChangeApplyHandler = Callable[[Session, dict[str, Any]], AppliedResource]


def _ensure_account_exists(db: Session, account_id: str | None) -> None:
    if account_id is None:
        return
    if db.get(Account, account_id) is None:
        raise ValueError("Account not found")


def _resolve_entity_value(
    db: Session,
    *,
    entity_id: str | None,
    entity_name: str | None,
) -> tuple[str | None, str | None]:
    normalized_name = normalize_entity_name(entity_name) if entity_name is not None else None
    if normalized_name == "":
        normalized_name = None

    if entity_id:
        entity = db.get(Entity, entity_id)
        if entity is None:
            raise ValueError("Entity not found")
        if normalized_name is not None and entity.name.lower() != normalized_name.lower():
            raise ValueError("Entity id and name do not match")
        return entity.id, entity.name

    if normalized_name is not None:
        entity = get_or_create_entity(db, normalized_name)
        return entity.id, entity.name

    return None, None


def _resolve_user_value(
    db: Session,
    *,
    user_id: str | None,
    user_name: str | None,
) -> tuple[str | None, str | None]:
    normalized_name = normalize_user_name(user_name) if user_name is not None else None
    if normalized_name == "":
        normalized_name = None

    if user_id:
        user = db.get(User, user_id)
        if user is None:
            raise ValueError("User not found")
        if normalized_name is not None and user.name.lower() != normalized_name.lower():
            raise ValueError("User id and name do not match")
        return user.id, user.name

    if normalized_name is not None:
        user = get_or_create_user(db, normalized_name)
        return user.id, user.name

    return None, None


def apply_create_tag(db: Session, payload: dict[str, Any]) -> AppliedResource:
    raw_name = str(payload.get("name") or "")
    normalized_name = normalize_tag_name(raw_name)
    if not normalized_name:
        raise ValueError("Tag name cannot be empty")
    existing = db.scalar(select(Tag).where(Tag.name == normalized_name))
    if existing is not None:
        return AppliedResource(resource_type="tag", resource_id=str(existing.id))

    tag = Tag(name=normalized_name, color=resolve_tag_color(payload.get("color")))
    db.add(tag)
    db.flush()
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_create_entity(db: Session, payload: dict[str, Any]) -> AppliedResource:
    raw_name = str(payload.get("name") or "")
    category = payload.get("category")
    entity = get_or_create_entity(db, raw_name, category=category if isinstance(category, str) or category is None else None)
    db.flush()
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_create_entry(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = EntryCreate.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    _ensure_account_exists(db, parsed.account_id)
    from_entity_id, from_entity_name = _resolve_entity_value(
        db,
        entity_id=parsed.from_entity_id,
        entity_name=parsed.from_entity,
    )
    to_entity_id, to_entity_name = _resolve_entity_value(
        db,
        entity_id=parsed.to_entity_id,
        entity_name=parsed.to_entity,
    )

    owner_user_id = parsed.owner_user_id
    owner_name = parsed.owner
    if owner_name is not None and normalize_user_name(owner_name) == "":
        owner_name = None
    if owner_user_id is None and owner_name is None:
        settings = get_settings()
        owner_user = ensure_current_user(db, settings.current_user_name)
        owner_user_id = owner_user.id
        owner_name = owner_user.name
    else:
        owner_user_id, owner_name = _resolve_user_value(
            db,
            user_id=owner_user_id,
            user_name=owner_name,
        )

    entry = Entry(
        account_id=parsed.account_id,
        kind=parsed.kind,
        occurred_at=parsed.occurred_at,
        name=parsed.name,
        amount_minor=parsed.amount_minor,
        currency_code=parsed.currency_code.upper(),
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        owner_user_id=owner_user_id,
        from_entity=from_entity_name,
        to_entity=to_entity_name,
        owner=owner_name,
        markdown_body=parsed.markdown_body,
        group_id="",
    )
    db.add(entry)
    assign_initial_group(db, entry)
    set_entry_tags(db, entry, parsed.tags)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


APPLY_CHANGE_HANDLERS: dict[AgentChangeType, ChangeApplyHandler] = {
    AgentChangeType.CREATE_ENTRY: apply_create_entry,
    AgentChangeType.CREATE_TAG: apply_create_tag,
    AgentChangeType.CREATE_ENTITY: apply_create_entity,
}


def apply_change_item_payload(db: Session, *, change_type: AgentChangeType, payload: dict[str, Any]) -> AppliedResource:
    handler = APPLY_CHANGE_HANDLERS.get(change_type)
    if handler is None:  # pragma: no cover - enum guard
        raise ValueError(f"Unsupported change type: {change_type}")
    return handler(db, payload)
