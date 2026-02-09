from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account, Entity, Entry
from backend.schemas import EntityCreate, EntityRead, EntityUpdate
from backend.services.entities import (
    find_entity_by_name,
    get_entity_category,
    get_or_create_entity,
    normalize_entity_name,
    set_entity_category,
)
from backend.services.taxonomy import get_single_term_name_map

router = APIRouter(prefix="/entities", tags=["entities"])


def _to_schema(
    entity: Entity,
    *,
    category: str | None = None,
    from_count: int | None = None,
    to_count: int | None = None,
    account_count: int | None = None,
    entry_count: int | None = None,
) -> EntityRead:
    return EntityRead(
        id=entity.id,
        name=entity.name,
        category=category if category is not None else entity.category,
        from_count=from_count,
        to_count=to_count,
        account_count=account_count,
        entry_count=entry_count,
    )


@router.get("", response_model=list[EntityRead])
def list_entities(db: Session = Depends(get_db)) -> list[EntityRead]:
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
            Account.entity_id == Entity.id,
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
    category_by_entity_id = get_single_term_name_map(
        db,
        taxonomy_key="entity_category",
        subject_type="entity",
        subject_ids=[entity.id for entity, *_ in rows],
    )
    return [
        _to_schema(
            entity,
            category=category_by_entity_id.get(entity.id) or entity.category,
            from_count=int(from_count or 0),
            to_count=int(to_count or 0),
            account_count=int(account_count or 0),
            entry_count=int(entry_count or 0),
        )
        for entity, from_count, to_count, account_count, entry_count in rows
    ]


@router.post("", response_model=EntityRead, status_code=status.HTTP_201_CREATED)
def create_entity(payload: EntityCreate, db: Session = Depends(get_db)) -> EntityRead:
    entity = get_or_create_entity(db, payload.name, category=payload.category)
    category = get_entity_category(db, entity)
    db.commit()
    db.refresh(entity)
    return _to_schema(entity, category=category)


@router.patch("/{entity_id}", response_model=EntityRead)
def update_entity(entity_id: str, payload: EntityUpdate, db: Session = Depends(get_db)) -> EntityRead:
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data:
        normalized_name = normalize_entity_name(update_data["name"] or "")
        if not normalized_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Entity name cannot be empty")

        existing = find_entity_by_name(db, normalized_name)
        if existing is not None and existing.id != entity.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entity name already exists")

        entity.name = normalized_name

        # Keep denormalized entry labels synchronized with entity renames.
        db.execute(update(Entry).where(Entry.from_entity_id == entity.id).values(from_entity=normalized_name))
        db.execute(update(Entry).where(Entry.to_entity_id == entity.id).values(to_entity=normalized_name))

    if "category" in update_data:
        set_entity_category(db, entity, update_data["category"])

    category = get_entity_category(db, entity)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return _to_schema(entity, category=category)
