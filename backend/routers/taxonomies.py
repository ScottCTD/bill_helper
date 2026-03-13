# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `taxonomies` routes.
# - Inputs: callers that import `backend/routers/taxonomies.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `taxonomies`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.schemas_finance import TaxonomyRead, TaxonomyTermCreate, TaxonomyTermRead, TaxonomyTermUpdate
from backend.services.taxonomy import (
    build_taxonomy_term_read,
    create_term_from_payload,
    list_taxonomy_reads,
    list_taxonomy_term_reads,
    update_term_from_payload,
)

router = APIRouter(prefix="/taxonomies", tags=["taxonomies"])


@router.get("", response_model=list[TaxonomyRead])
def list_taxonomies(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[TaxonomyRead]:
    rows = list_taxonomy_reads(db, principal=principal)
    db.commit()
    return rows


@router.get("/{taxonomy_key}/terms", response_model=list[TaxonomyTermRead])
def list_taxonomy_terms(
    taxonomy_key: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[TaxonomyTermRead]:
    return list_taxonomy_term_reads(db, taxonomy_key=taxonomy_key, principal=principal)


@router.post("/{taxonomy_key}/terms", response_model=TaxonomyTermRead, status_code=status.HTTP_201_CREATED)
def create_taxonomy_term(
    taxonomy_key: str,
    payload: TaxonomyTermCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> TaxonomyTermRead:
    term = create_term_from_payload(
        db,
        taxonomy_key=taxonomy_key,
        name=payload.name,
        description=payload.description,
        principal=principal,
    )

    db.commit()
    db.refresh(term)
    return build_taxonomy_term_read(db, term=term)


@router.patch("/{taxonomy_key}/terms/{term_id}", response_model=TaxonomyTermRead)
def update_taxonomy_term(
    taxonomy_key: str,
    term_id: str,
    payload: TaxonomyTermUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> TaxonomyTermRead:
    term = update_term_from_payload(
        db,
        taxonomy_key=taxonomy_key,
        term_id=term_id,
        name=payload.name,
        description=payload.description,
        fields_set=set(payload.model_dump(exclude_unset=True)),
        principal=principal,
    )

    db.commit()
    db.refresh(term)
    return build_taxonomy_term_read(db, term=term)
