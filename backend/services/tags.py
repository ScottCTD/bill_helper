from __future__ import annotations

import colorsys
import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models_finance import Entry, EntryTag, Tag
from backend.schemas_finance import TagCreate, TagRead, TagUpdate
from backend.services.crud_policy import PolicyViolation, assert_unique_name, normalize_required_name
from backend.services.taxonomy_constants import (
    TAG_TYPE_SUBJECT_TYPE,
    TAG_TYPE_TAXONOMY_KEY,
)
from backend.services.taxonomy import assign_single_term_by_name, get_single_term_name, get_single_term_name_map

_RNG = random.SystemRandom()


def _normalize_tag_name(name: str) -> str:
    return name.strip().lower()


def normalize_tag_color(color: str | None) -> str | None:
    if color is None:
        return None
    normalized = color.strip()
    return normalized or None


def generate_random_tag_color() -> str:
    # Pastel-ish HLS palette keeps tag chips readable.
    hue = _RNG.random()
    lightness = _RNG.uniform(0.62, 0.74)
    saturation = _RNG.uniform(0.45, 0.7)
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}"


def resolve_tag_color(color: str | None) -> str:
    normalized = normalize_tag_color(color)
    if normalized is not None:
        return normalized
    return generate_random_tag_color()


def create_tag_from_payload(db: Session, *, payload: TagCreate) -> Tag:
    normalized_name = normalize_required_name(
        payload.name,
        normalizer=_normalize_tag_name,
        empty_detail="Tag name cannot be empty",
    )
    existing = db.scalar(select(Tag).where(Tag.name == normalized_name))
    assert_unique_name(
        existing_id=existing.id if existing is not None else None,
        current_id=None,
        conflict_detail="Tag already exists",
    )

    tag = Tag(
        name=normalized_name,
        color=resolve_tag_color(payload.color),
        description=payload.description,
    )
    db.add(tag)
    db.flush()
    assign_single_term_by_name(
        db,
        taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
        subject_type=TAG_TYPE_SUBJECT_TYPE,
        subject_id=tag.id,
        term_name=payload.type,
    )
    return tag


def load_tag(db: Session, *, tag_id: int) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise PolicyViolation.not_found("Tag not found")
    return tag


def update_tag_from_payload(db: Session, *, tag: Tag, payload: TagUpdate) -> Tag:
    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data:
        normalized_name = normalize_required_name(
            update_data["name"],
            normalizer=_normalize_tag_name,
            empty_detail="Tag name cannot be empty",
        )
        existing = db.scalar(select(Tag).where(Tag.name == normalized_name))
        assert_unique_name(
            existing_id=existing.id if existing is not None else None,
            current_id=tag.id,
            conflict_detail="Tag already exists",
        )
        tag.name = normalized_name
    if "color" in update_data:
        tag.color = update_data["color"]
    if "description" in update_data:
        tag.description = update_data["description"]
    if "type" in update_data:
        assign_single_term_by_name(
            db,
            taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
            subject_type=TAG_TYPE_SUBJECT_TYPE,
            subject_id=tag.id,
            term_name=update_data["type"],
        )
    db.add(tag)
    db.flush()
    return tag


def count_entries_for_tag(db: Session, *, tag_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(EntryTag.entry_id))
            .select_from(EntryTag)
            .join(Entry, Entry.id == EntryTag.entry_id)
            .where(
                EntryTag.tag_id == tag_id,
                Entry.is_deleted.is_(False),
            )
        )
        or 0
    )


def build_tag_read(
    db: Session,
    *,
    tag: Tag,
    entry_count: int | None = None,
) -> TagRead:
    resolved_entry_count = count_entries_for_tag(db, tag_id=tag.id) if entry_count is None else entry_count
    return TagRead(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        description=tag.description,
        type=get_single_term_name(
            db,
            taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
            subject_type=TAG_TYPE_SUBJECT_TYPE,
            subject_id=tag.id,
        ),
        entry_count=resolved_entry_count,
    )


def list_tag_reads(db: Session) -> list[TagRead]:
    entry_count_subquery = (
        select(func.count(EntryTag.entry_id))
        .select_from(EntryTag)
        .join(Entry, Entry.id == EntryTag.entry_id)
        .where(
            EntryTag.tag_id == Tag.id,
            Entry.is_deleted.is_(False),
        )
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            Tag,
            entry_count_subquery.label("entry_count"),
        ).order_by(Tag.name.asc())
    ).all()
    type_by_tag_id = get_single_term_name_map(
        db,
        taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
        subject_type=TAG_TYPE_SUBJECT_TYPE,
        subject_ids=[tag.id for tag, _ in rows],
    )
    return [
        TagRead(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            description=tag.description,
            type=type_by_tag_id.get(str(tag.id)),
            entry_count=int(entry_count or 0),
        )
        for tag, entry_count in rows
    ]


def delete_tag(db: Session, *, tag: Tag) -> None:
    assign_single_term_by_name(
        db,
        taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
        subject_type=TAG_TYPE_SUBJECT_TYPE,
        subject_id=tag.id,
        term_name=None,
    )
    db.delete(tag)
    db.flush()
