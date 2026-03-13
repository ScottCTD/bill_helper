# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `entities` routes.
# - Inputs: callers that import `backend/routers/entities.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `entities`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.schemas_finance import EntityCreate, EntityRead, EntityUpdate
from backend.services.access_scope import load_entity_for_principal
from backend.services.entities import (
    create_entity as create_entity_service,
    delete_entity_and_preserve_labels,
    list_entities_with_usage,
    read_entity_category,
    update_entity as update_entity_service,
)
from backend.services.finance_contracts import EntityCreateCommand, EntityPatch
router = APIRouter(prefix="/entities", tags=["entities"])


@dataclass(frozen=True, slots=True)
class _EntityUsageCounts:
    is_account: bool = False
    from_count: int | None = None
    to_count: int | None = None
    account_count: int | None = None
    entry_count: int | None = None
    net_amount_minor: int | None = None
    net_amount_currency_code: str | None = None
    net_amount_mixed_currencies: bool = False


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
        is_account=usage_counts.is_account,
        from_count=usage_counts.from_count,
        to_count=usage_counts.to_count,
        account_count=usage_counts.account_count,
        entry_count=usage_counts.entry_count,
        net_amount_minor=usage_counts.net_amount_minor,
        net_amount_currency_code=usage_counts.net_amount_currency_code,
        net_amount_mixed_currencies=usage_counts.net_amount_mixed_currencies,
    )


@router.get("", response_model=list[EntityRead])
def list_entities(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[EntityRead]:
    rows = list_entities_with_usage(db, principal=principal)
    return [
        _to_schema(
            row.entity,
            category=read_entity_category(db, row.entity),
            usage=_EntityUsageCounts(
                is_account=row.is_account,
                from_count=row.from_count,
                to_count=row.to_count,
                account_count=row.account_count,
                entry_count=row.entry_count,
                net_amount_minor=row.net_amount_minor,
                net_amount_currency_code=row.net_amount_currency_code,
                net_amount_mixed_currencies=row.net_amount_mixed_currencies,
            ),
        )
        for row in rows
    ]


@router.post("", response_model=EntityRead, status_code=status.HTTP_201_CREATED)
def create_entity(
    payload: EntityCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> EntityRead:
    entity = create_entity_service(
        db,
        command=EntityCreateCommand.model_validate(payload.model_dump()),
        principal=principal,
    )
    category = read_entity_category(db, entity)
    db.commit()
    db.refresh(entity)
    return _to_schema(entity, category=category)


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(
    entity_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    entity = load_entity_for_principal(db, entity_id=entity_id, principal=principal)
    delete_entity_and_preserve_labels(db, entity=entity)
    db.commit()


@router.patch("/{entity_id}", response_model=EntityRead)
def update_entity(
    entity_id: str,
    payload: EntityUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> EntityRead:
    entity = load_entity_for_principal(db, entity_id=entity_id, principal=principal)
    update_entity_service(
        db,
        entity=entity,
        patch=EntityPatch.model_validate(payload.model_dump(exclude_unset=True)),
    )

    category = read_entity_category(db, entity)
    db.commit()
    db.refresh(entity)
    return _to_schema(entity, category=category)
