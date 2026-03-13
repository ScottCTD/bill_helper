# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `filter_groups` routes.
# - Inputs: callers that import `backend/routers/filter_groups.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `filter_groups`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.schemas_finance import FilterGroupCreate, FilterGroupRead, FilterGroupUpdate
from backend.services.filter_groups import (
    build_filter_group_read,
    create_filter_group,
    delete_filter_group,
    list_filter_group_reads,
    update_filter_group,
)

router = APIRouter(prefix="/filter-groups", tags=["filter-groups"])


@router.get("", response_model=list[FilterGroupRead])
def list_filter_groups(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[FilterGroupRead]:
    rows = list_filter_group_reads(db, principal=principal)
    db.commit()
    return rows


@router.post("", response_model=FilterGroupRead, status_code=status.HTTP_201_CREATED)
def create_filter_group_endpoint(
    payload: FilterGroupCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> FilterGroupRead:
    filter_group = create_filter_group(db, payload=payload, principal=principal)
    db.commit()
    return build_filter_group_read(filter_group)


@router.patch("/{filter_group_id}", response_model=FilterGroupRead)
def update_filter_group_endpoint(
    filter_group_id: str,
    payload: FilterGroupUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> FilterGroupRead:
    filter_group = update_filter_group(
        db,
        filter_group_id=filter_group_id,
        payload=payload,
        principal=principal,
    )
    db.commit()
    return build_filter_group_read(filter_group)


@router.delete("/{filter_group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_filter_group_endpoint(
    filter_group_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    delete_filter_group(db, filter_group_id=filter_group_id, principal=principal)
    db.commit()
