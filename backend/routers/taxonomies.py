from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Taxonomy, TaxonomyAssignment, TaxonomyTerm
from backend.schemas import TaxonomyRead, TaxonomyTermCreate, TaxonomyTermRead, TaxonomyTermUpdate
from backend.services.taxonomy import (
    ensure_default_taxonomies,
    get_or_create_term,
    get_taxonomy_by_key,
    list_terms_with_usage,
    rename_term,
)

router = APIRouter(prefix="/taxonomies", tags=["taxonomies"])


def _get_taxonomy_or_404(db: Session, taxonomy_key: str) -> Taxonomy:
    taxonomy = get_taxonomy_by_key(db, taxonomy_key)
    if taxonomy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy not found")
    return taxonomy


def _term_to_schema(db: Session, term: TaxonomyTerm) -> TaxonomyTermRead:
    usage_count = int(
        db.scalar(
            select(func.count(TaxonomyAssignment.id)).where(TaxonomyAssignment.term_id == term.id)
        )
        or 0
    )
    return TaxonomyTermRead(
        id=term.id,
        taxonomy_id=term.taxonomy_id,
        name=term.name,
        normalized_name=term.normalized_name,
        parent_term_id=term.parent_term_id,
        usage_count=usage_count,
    )


@router.get("", response_model=list[TaxonomyRead])
def list_taxonomies(db: Session = Depends(get_db)) -> list[TaxonomyRead]:
    ensure_default_taxonomies(db)
    db.commit()
    rows = list(db.scalars(select(Taxonomy).order_by(Taxonomy.key.asc())))
    return [TaxonomyRead.model_validate(row) for row in rows]


@router.get("/{taxonomy_key}/terms", response_model=list[TaxonomyTermRead])
def list_taxonomy_terms(taxonomy_key: str, db: Session = Depends(get_db)) -> list[TaxonomyTermRead]:
    taxonomy = _get_taxonomy_or_404(db, taxonomy_key)
    rows = list_terms_with_usage(db, taxonomy=taxonomy)
    return [
        TaxonomyTermRead(
            id=term.id,
            taxonomy_id=term.taxonomy_id,
            name=term.name,
            normalized_name=term.normalized_name,
            parent_term_id=term.parent_term_id,
            usage_count=usage_count,
        )
        for term, usage_count in rows
    ]


@router.post("/{taxonomy_key}/terms", response_model=TaxonomyTermRead, status_code=status.HTTP_201_CREATED)
def create_taxonomy_term(
    taxonomy_key: str,
    payload: TaxonomyTermCreate,
    db: Session = Depends(get_db),
) -> TaxonomyTermRead:
    taxonomy = _get_taxonomy_or_404(db, taxonomy_key)

    try:
        term = get_or_create_term(
            db,
            taxonomy=taxonomy,
            name=payload.name,
            parent_term_id=payload.parent_term_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    db.refresh(term)
    return _term_to_schema(db, term)


@router.patch("/{taxonomy_key}/terms/{term_id}", response_model=TaxonomyTermRead)
def update_taxonomy_term(
    taxonomy_key: str,
    term_id: str,
    payload: TaxonomyTermUpdate,
    db: Session = Depends(get_db),
) -> TaxonomyTermRead:
    taxonomy = _get_taxonomy_or_404(db, taxonomy_key)
    term = db.scalar(
        select(TaxonomyTerm).where(
            TaxonomyTerm.id == term_id,
            TaxonomyTerm.taxonomy_id == taxonomy.id,
        )
    )
    if term is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxonomy term not found")

    if payload.name is not None:
        try:
            rename_term(db, term=term, new_name=payload.name)
        except ValueError as exc:
            message = str(exc)
            if "already exists" in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    db.commit()
    db.refresh(term)
    return _term_to_schema(db, term)
