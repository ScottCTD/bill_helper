from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal, require_admin_principal
from backend.database import get_db
from backend.models_finance import Entity
from backend.schemas_finance import EntityCreate, EntityRead, EntityUpdate
from backend.services.crud_policy import (
    PolicyViolation,
    translate_policy_violation,
)
from backend.services.entities import (
    create_entity_from_payload,
    list_entities_with_usage,
    read_entity_category,
    update_entity_from_payload,
)
from backend.services.taxonomy import get_single_term_name_map

router = APIRouter(prefix="/entities", tags=["entities"])


@dataclass(frozen=True, slots=True)
class _EntityUsageCounts:
    from_count: int | None = None
    to_count: int | None = None
    account_count: int | None = None
    entry_count: int | None = None


def _to_schema(
    entity: Entity,
    *,
    category: str | None = None,
    usage: _EntityUsageCounts | None = None,
) -> EntityRead:
    usage_counts = usage or _EntityUsageCounts()
    return EntityRead(
        id=entity.id,
        name=entity.name,
        category=category if category is not None else entity.category,
        from_count=usage_counts.from_count,
        to_count=usage_counts.to_count,
        account_count=usage_counts.account_count,
        entry_count=usage_counts.entry_count,
    )


@router.get("", response_model=list[EntityRead])
def list_entities(db: Session = Depends(get_db)) -> list[EntityRead]:
    rows = list_entities_with_usage(db)
    category_by_entity_id = get_single_term_name_map(
        db,
        taxonomy_key="entity_category",
        subject_type="entity",
        subject_ids=[row.entity.id for row in rows],
    )
    return [
        _to_schema(
            row.entity,
            category=category_by_entity_id.get(row.entity.id) or row.entity.category,
            usage=_EntityUsageCounts(
                from_count=row.from_count,
                to_count=row.to_count,
                account_count=row.account_count,
                entry_count=row.entry_count,
            ),
        )
        for row in rows
    ]


@router.post("", response_model=EntityRead, status_code=status.HTTP_201_CREATED)
def create_entity(
    payload: EntityCreate,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> EntityRead:
    entity = create_entity_from_payload(db, payload=payload)
    category = read_entity_category(db, entity)
    db.commit()
    db.refresh(entity)
    return _to_schema(entity, category=category)


@router.patch("/{entity_id}", response_model=EntityRead)
def update_entity(
    entity_id: str,
    payload: EntityUpdate,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> EntityRead:
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    try:
        update_entity_from_payload(
            db,
            entity=entity,
            payload=payload,
        )
    except PolicyViolation as exc:
        raise translate_policy_violation(exc) from exc

    category = read_entity_category(db, entity)
    db.commit()
    db.refresh(entity)
    return _to_schema(entity, category=category)
