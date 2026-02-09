from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import Entity
from backend.services.taxonomy import assign_single_term_by_name, get_single_term_name


ENTITY_CATEGORY_TAXONOMY_KEY = "entity_category"
ENTITY_CATEGORY_SUBJECT_TYPE = "entity"


def normalize_entity_name(name: str) -> str:
    return " ".join(name.split()).strip()


def normalize_entity_category(category: str | None) -> str | None:
    if category is None:
        return None
    normalized = " ".join(category.split()).strip().lower()
    return normalized or None


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


def get_entity_category(db: Session, entity: Entity) -> str | None:
    category = get_single_term_name(
        db,
        taxonomy_key=ENTITY_CATEGORY_TAXONOMY_KEY,
        subject_type=ENTITY_CATEGORY_SUBJECT_TYPE,
        subject_id=entity.id,
    )
    if category is not None:
        if entity.category != category:
            entity.category = category
            db.add(entity)
            db.flush()
        return category
    if entity.category:
        # Backfill pre-taxonomy values lazily.
        set_entity_category(db, entity, entity.category)
        return entity.category
    return None


def find_entity_by_name(db: Session, name: str) -> Entity | None:
    normalized = normalize_entity_name(name)
    if not normalized:
        return None
    return db.scalar(select(Entity).where(func.lower(Entity.name) == normalized.lower()))


def get_or_create_entity(db: Session, name: str, *, category: str | None = None) -> Entity:
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
