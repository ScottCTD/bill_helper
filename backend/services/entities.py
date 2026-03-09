from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from backend.models_finance import Account, Entity, Entry
from backend.schemas_finance import EntityCreate, EntityUpdate
from backend.services.crud_policy import (
    PolicyViolation,
    assert_unique_name,
    normalize_required_name,
)
from backend.services.taxonomy_constants import (
    ENTITY_CATEGORY_SUBJECT_TYPE,
    ENTITY_CATEGORY_TAXONOMY_KEY,
)
from backend.services.taxonomy import assign_single_term_by_name, get_single_term_name


ACCOUNT_CATEGORY_DETAIL = "Account category is reserved for Accounts. Use /accounts instead."


@dataclass(frozen=True, slots=True)
class EntityUsageRow:
    entity: Entity
    is_account: bool
    from_count: int
    to_count: int
    account_count: int
    entry_count: int


def normalize_entity_name(name: str) -> str:
    return " ".join(name.split()).strip()


def normalize_entity_category(category: str | None) -> str | None:
    if category is None:
        return None
    normalized = " ".join(category.split()).strip().lower()
    return normalized or None


def ensure_entity_category_is_not_account(category: str | None) -> None:
    if normalize_entity_category(category) == "account":
        raise PolicyViolation.conflict(ACCOUNT_CATEGORY_DETAIL)


def set_entity_category(db: Session, entity: Entity, category: str | None) -> str | None:
    normalized = normalize_entity_category(category)
    assign_single_term_by_name(
        db,
        taxonomy_key=ENTITY_CATEGORY_TAXONOMY_KEY,
        subject_type=ENTITY_CATEGORY_SUBJECT_TYPE,
        subject_id=entity.id,
        term_name=normalized,
    )
    entity.category = normalized
    db.add(entity)
    db.flush()
    return normalized


def read_entity_category(db: Session, entity: Entity) -> str | None:
    category = get_single_term_name(
        db,
        taxonomy_key=ENTITY_CATEGORY_TAXONOMY_KEY,
        subject_type=ENTITY_CATEGORY_SUBJECT_TYPE,
        subject_id=entity.id,
    )
    if category is not None:
        return category
    return entity.category


def clear_entity_category(db: Session, entity: Entity) -> None:
    assign_single_term_by_name(
        db,
        taxonomy_key=ENTITY_CATEGORY_TAXONOMY_KEY,
        subject_type=ENTITY_CATEGORY_SUBJECT_TYPE,
        subject_id=entity.id,
        term_name=None,
    )
    entity.category = None
    db.add(entity)
    db.flush()


def find_entity_by_name(db: Session, name: str) -> Entity | None:
    normalized = normalize_entity_name(name)
    if not normalized:
        return None
    return db.scalar(select(Entity).where(func.lower(Entity.name) == normalized.lower()))


def ensure_entity_by_name(db: Session, name: str, *, category: str | None = None) -> Entity:
    normalized = normalize_entity_name(name)
    if not normalized:
        raise ValueError("Entity name cannot be empty")
    normalized_category = normalize_entity_category(category)

    existing = find_entity_by_name(db, normalized)
    if existing is not None:
        if normalized_category is not None and not existing.category:
            set_entity_category(db, existing, normalized_category)
        return existing

    entity = Entity(name=normalized, category=None)
    db.add(entity)
    db.flush()
    if normalized_category is not None:
        set_entity_category(db, entity, normalized_category)
    return entity


def is_account_entity(entity: Entity) -> bool:
    return entity.account is not None


def ensure_entity_is_not_account_backed(entity: Entity) -> None:
    if is_account_entity(entity):
        raise PolicyViolation.conflict("Account-backed entities must be managed from Accounts")


def list_entities_with_usage(db: Session) -> list[EntityUsageRow]:
    from_count_subquery = (
        select(func.count(Entry.id))
        .where(
            Entry.is_deleted.is_(False),
            Entry.from_entity_id == Entity.id,
        )
        .scalar_subquery()
    )
    to_count_subquery = (
        select(func.count(Entry.id))
        .where(
            Entry.is_deleted.is_(False),
            Entry.to_entity_id == Entity.id,
        )
        .scalar_subquery()
    )
    account_count_subquery = (
        select(func.count(Account.id))
        .where(
            Account.id == Entity.id,
        )
        .scalar_subquery()
    )
    entry_count_subquery = (
        select(func.count(Entry.id))
        .where(
            Entry.is_deleted.is_(False),
            or_(
                Entry.from_entity_id == Entity.id,
                Entry.to_entity_id == Entity.id,
            ),
        )
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            Entity,
            from_count_subquery.label("from_count"),
            to_count_subquery.label("to_count"),
            account_count_subquery.label("account_count"),
            entry_count_subquery.label("entry_count"),
        ).order_by(func.lower(Entity.name).asc())
    ).all()
    return [
        EntityUsageRow(
            entity=entity,
            is_account=int(account_count or 0) > 0,
            from_count=int(from_count or 0),
            to_count=int(to_count or 0),
            account_count=int(account_count or 0),
            entry_count=int(entry_count or 0),
        )
        for entity, from_count, to_count, account_count, entry_count in rows
    ]


def create_entity_from_payload(db: Session, *, payload: EntityCreate) -> Entity:
    normalized_name = normalize_required_name(
        payload.name,
        normalizer=normalize_entity_name,
        empty_detail="Entity name cannot be empty",
    )
    ensure_entity_category_is_not_account(payload.category)
    existing = find_entity_by_name(db, normalized_name)
    assert_unique_name(
        existing_id=existing.id if existing is not None else None,
        current_id=None,
        conflict_detail="Entity name already exists",
    )
    entity = Entity(name=normalized_name, category=None)
    db.add(entity)
    db.flush()
    if payload.category is not None:
        set_entity_category(db, entity, payload.category)
    return entity


def rename_entity_and_sync_entry_labels(
    db: Session,
    *,
    entity: Entity,
    raw_name: str,
) -> Entity:
    normalized_name = normalize_required_name(
        raw_name,
        normalizer=normalize_entity_name,
        empty_detail="Entity name cannot be empty",
    )
    existing = find_entity_by_name(db, normalized_name)
    assert_unique_name(
        existing_id=existing.id if existing is not None else None,
        current_id=entity.id,
        conflict_detail="Entity name already exists",
    )
    entity.name = normalized_name
    db.execute(
        update(Entry)
        .where(Entry.from_entity_id == entity.id)
        .values(from_entity=normalized_name)
    )
    db.execute(
        update(Entry)
        .where(Entry.to_entity_id == entity.id)
        .values(to_entity=normalized_name)
    )
    db.add(entity)
    db.flush()
    return entity


def update_entity_from_payload(
    db: Session,
    *,
    entity: Entity,
    payload: EntityUpdate,
) -> Entity:
    ensure_entity_is_not_account_backed(entity)
    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data:
        rename_entity_and_sync_entry_labels(
            db,
            entity=entity,
            raw_name=update_data["name"],
        )

    if "category" in update_data:
        ensure_entity_category_is_not_account(update_data["category"])
        set_entity_category(db, entity, update_data["category"])

    db.add(entity)
    db.flush()
    return entity


def detach_entity_references_preserve_labels(db: Session, *, entity: Entity) -> None:
    db.execute(
        update(Entry)
        .where(Entry.from_entity_id == entity.id)
        .values(from_entity_id=None)
    )
    db.execute(
        update(Entry)
        .where(Entry.to_entity_id == entity.id)
        .values(to_entity_id=None)
    )


def delete_entity_and_preserve_labels(db: Session, *, entity: Entity) -> None:
    ensure_entity_is_not_account_backed(entity)
    detach_entity_references_preserve_labels(db, entity=entity)
    clear_entity_category(db, entity)
    db.delete(entity)
    db.flush()
