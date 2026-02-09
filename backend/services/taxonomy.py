from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.models import Taxonomy, TaxonomyAssignment, TaxonomyTerm


@dataclass(frozen=True, slots=True)
class TaxonomySpec:
    applies_to: str
    cardinality: str
    display_name: str


DEFAULT_TAXONOMY_SPECS: dict[str, TaxonomySpec] = {
    "entity_category": TaxonomySpec(
        applies_to="entity",
        cardinality="single",
        display_name="Entity Categories",
    ),
    "tag_category": TaxonomySpec(
        applies_to="tag",
        cardinality="single",
        display_name="Tag Categories",
    ),
}


def normalize_taxonomy_key(key: str) -> str:
    return "_".join(key.strip().lower().split())


def normalize_term_name(name: str) -> str:
    return " ".join(name.split()).strip().lower()


def ensure_taxonomy(
    db: Session,
    *,
    key: str,
    applies_to: str,
    cardinality: str,
    display_name: str,
) -> Taxonomy:
    normalized_key = normalize_taxonomy_key(key)
    taxonomy = db.scalar(select(Taxonomy).where(Taxonomy.key == normalized_key))
    if taxonomy is not None:
        return taxonomy

    taxonomy = Taxonomy(
        key=normalized_key,
        applies_to=applies_to,
        cardinality=cardinality,
        display_name=display_name,
    )
    db.add(taxonomy)
    db.flush()
    return taxonomy


def ensure_default_taxonomies(db: Session) -> dict[str, Taxonomy]:
    taxonomies: dict[str, Taxonomy] = {}
    for key, spec in DEFAULT_TAXONOMY_SPECS.items():
        taxonomies[key] = ensure_taxonomy(
            db,
            key=key,
            applies_to=spec.applies_to,
            cardinality=spec.cardinality,
            display_name=spec.display_name,
        )
    return taxonomies


def get_taxonomy_by_key(db: Session, key: str, *, create_default: bool = True) -> Taxonomy | None:
    normalized_key = normalize_taxonomy_key(key)
    taxonomy = db.scalar(select(Taxonomy).where(Taxonomy.key == normalized_key))
    if taxonomy is not None:
        return taxonomy

    spec = DEFAULT_TAXONOMY_SPECS.get(normalized_key)
    if spec is None:
        return None
    if not create_default:
        return None
    return ensure_taxonomy(
        db,
        key=normalized_key,
        applies_to=spec.applies_to,
        cardinality=spec.cardinality,
        display_name=spec.display_name,
    )


def get_or_create_term(db: Session, *, taxonomy: Taxonomy, name: str, parent_term_id: str | None = None) -> TaxonomyTerm:
    normalized_name = normalize_term_name(name)
    if not normalized_name:
        raise ValueError("Term name cannot be empty")

    term = db.scalar(
        select(TaxonomyTerm).where(
            TaxonomyTerm.taxonomy_id == taxonomy.id,
            TaxonomyTerm.normalized_name == normalized_name,
        )
    )
    if term is not None:
        return term

    term = TaxonomyTerm(
        taxonomy_id=taxonomy.id,
        name=normalized_name,
        normalized_name=normalized_name,
        parent_term_id=parent_term_id,
    )
    db.add(term)
    db.flush()
    return term


def rename_term(db: Session, *, term: TaxonomyTerm, new_name: str) -> TaxonomyTerm:
    normalized_name = normalize_term_name(new_name)
    if not normalized_name:
        raise ValueError("Term name cannot be empty")

    existing = db.scalar(
        select(TaxonomyTerm).where(
            TaxonomyTerm.taxonomy_id == term.taxonomy_id,
            TaxonomyTerm.normalized_name == normalized_name,
        )
    )
    if existing is not None and existing.id != term.id:
        raise ValueError("Term already exists")

    term.name = normalized_name
    term.normalized_name = normalized_name
    db.add(term)
    db.flush()
    return term


def assign_single_term_by_name(
    db: Session,
    *,
    taxonomy_key: str,
    subject_type: str,
    subject_id: str | int,
    term_name: str | None,
) -> TaxonomyTerm | None:
    taxonomy = get_taxonomy_by_key(db, taxonomy_key)
    if taxonomy is None:
        raise ValueError(f"Unknown taxonomy '{taxonomy_key}'")

    normalized_term_name = normalize_term_name(term_name or "") if term_name is not None else ""
    subject_id_str = str(subject_id)

    db.execute(
        delete(TaxonomyAssignment).where(
            TaxonomyAssignment.taxonomy_id == taxonomy.id,
            TaxonomyAssignment.subject_type == subject_type,
            TaxonomyAssignment.subject_id == subject_id_str,
        )
    )

    if not normalized_term_name:
        db.flush()
        return None

    term = get_or_create_term(db, taxonomy=taxonomy, name=normalized_term_name)
    assignment = TaxonomyAssignment(
        taxonomy_id=taxonomy.id,
        term_id=term.id,
        subject_type=subject_type,
        subject_id=subject_id_str,
    )
    db.add(assignment)
    db.flush()
    return term


def get_single_term_name(db: Session, *, taxonomy_key: str, subject_type: str, subject_id: str | int) -> str | None:
    taxonomy = get_taxonomy_by_key(db, taxonomy_key, create_default=False)
    if taxonomy is None:
        return None

    row = db.execute(
        select(TaxonomyTerm.name)
        .join(TaxonomyAssignment, TaxonomyAssignment.term_id == TaxonomyTerm.id)
        .where(
            TaxonomyAssignment.taxonomy_id == taxonomy.id,
            TaxonomyAssignment.subject_type == subject_type,
            TaxonomyAssignment.subject_id == str(subject_id),
        )
        .limit(1)
    ).first()
    return str(row[0]) if row else None


def get_single_term_name_map(
    db: Session,
    *,
    taxonomy_key: str,
    subject_type: str,
    subject_ids: list[str | int],
) -> dict[str, str]:
    taxonomy = get_taxonomy_by_key(db, taxonomy_key, create_default=False)
    if taxonomy is None:
        return {}
    if not subject_ids:
        return {}

    subject_id_values = [str(value) for value in subject_ids]
    rows = db.execute(
        select(
            TaxonomyAssignment.subject_id,
            TaxonomyTerm.name,
        )
        .join(TaxonomyTerm, TaxonomyTerm.id == TaxonomyAssignment.term_id)
        .where(
            TaxonomyAssignment.taxonomy_id == taxonomy.id,
            TaxonomyAssignment.subject_type == subject_type,
            TaxonomyAssignment.subject_id.in_(subject_id_values),
        )
    ).all()
    return {str(subject_id): str(name) for subject_id, name in rows}


def list_terms_with_usage(
    db: Session,
    *,
    taxonomy: Taxonomy,
) -> list[tuple[TaxonomyTerm, int]]:
    rows = db.execute(
        select(
            TaxonomyTerm,
            func.count(TaxonomyAssignment.id).label("usage_count"),
        )
        .outerjoin(TaxonomyAssignment, TaxonomyAssignment.term_id == TaxonomyTerm.id)
        .where(TaxonomyTerm.taxonomy_id == taxonomy.id)
        .group_by(TaxonomyTerm.id)
        .order_by(func.lower(TaxonomyTerm.name).asc())
    ).all()
    return [(term, int(usage_count or 0)) for term, usage_count in rows]
