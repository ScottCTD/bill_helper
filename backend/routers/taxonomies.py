from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal, require_admin_principal
from backend.database import get_db
from backend.models_finance import Taxonomy, TaxonomyAssignment, TaxonomyTerm
from backend.schemas_finance import TaxonomyRead, TaxonomyTermCreate, TaxonomyTermRead, TaxonomyTermUpdate
from backend.services.crud_policy import map_value_error, translate_policy_violation
from backend.services.taxonomy import (
    create_term,
    ensure_default_taxonomies,
    ensure_taxonomy_by_key,
    get_term_description,
    get_taxonomy_by_key,
    list_terms_with_usage,
    rename_term,
)

router = APIRouter(prefix="/taxonomies", tags=["taxonomies"])


def _set_term_description(term: TaxonomyTerm, description: str | None) -> None:
    normalized = " ".join(description.split()).strip() if description is not None else ""
    metadata = dict(term.metadata_json) if isinstance(term.metadata_json, dict) else {}
    if normalized:
        metadata["description"] = normalized
    else:
        metadata.pop("description", None)
    term.metadata_json = metadata or None


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
        description=get_term_description(term),
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
            description=get_term_description(term),
            usage_count=usage_count,
        )
        for term, usage_count in rows
    ]


@router.post("/{taxonomy_key}/terms", response_model=TaxonomyTermRead, status_code=status.HTTP_201_CREATED)
def create_taxonomy_term(
    taxonomy_key: str,
    payload: TaxonomyTermCreate,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> TaxonomyTermRead:
    try:
        taxonomy = ensure_taxonomy_by_key(db, taxonomy_key)
        term = create_term(
            db,
            taxonomy=taxonomy,
            name=payload.name,
        )
        if payload.description is not None:
            _set_term_description(term, payload.description)
            db.add(term)
    except ValueError as exc:
        violation = map_value_error(
            exc,
            not_found_patterns=("Unknown taxonomy",),
            conflict_patterns=("already exists",),
        )
        if violation.status_code == status.HTTP_404_NOT_FOUND:
            violation.detail = "Taxonomy not found"
        raise translate_policy_violation(violation) from exc

    db.commit()
    db.refresh(term)
    return _term_to_schema(db, term)


@router.patch("/{taxonomy_key}/terms/{term_id}", response_model=TaxonomyTermRead)
def update_taxonomy_term(
    taxonomy_key: str,
    term_id: str,
    payload: TaxonomyTermUpdate,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
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
            violation = map_value_error(
                exc,
                conflict_patterns=("already exists",),
            )
            raise translate_policy_violation(violation) from exc
    if "description" in payload.model_dump(exclude_unset=True):
        _set_term_description(term, payload.description)
        db.add(term)

    db.commit()
    db.refresh(term)
    return _term_to_schema(db, term)
