from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.enums_finance import EntryKind
from backend.models_finance import Entry, EntryGroupMember, Tag
from backend.services.tags import generate_random_tag_color


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def signed_amount_minor(kind: EntryKind, amount_minor: int) -> int:
    if kind == EntryKind.INCOME:
        return amount_minor
    return -amount_minor


def normalize_tag_name(name: str) -> str:
    return name.strip().lower()


def normalize_required_tag_name(name: str) -> str:
    normalized = normalize_tag_name(name)
    if not normalized:
        raise ValueError("Tag name cannot be empty")
    return normalized


def ensure_tags(db: Session, tag_names: list[str]) -> list[Tag]:
    normalized_names = sorted({normalize_required_tag_name(name) for name in tag_names})
    if not normalized_names:
        return []

    existing_tags = list(db.scalars(select(Tag).where(Tag.name.in_(normalized_names))))
    existing_by_name = {tag.name: tag for tag in existing_tags}

    tags: list[Tag] = []
    for name in normalized_names:
        tag = existing_by_name.get(name)
        if tag is None:
            tag = Tag(name=name, color=generate_random_tag_color())
            db.add(tag)
            db.flush()
        tags.append(tag)

    return tags


def set_entry_tags(db: Session, entry: Entry, tag_names: list[str]) -> None:
    entry.tags = ensure_tags(db, tag_names)


def soft_delete_entry(db: Session, entry: Entry) -> None:
    entry.is_deleted = True
    entry.deleted_at = utc_now()
    db.execute(
        delete(EntryGroupMember).where(EntryGroupMember.entry_id == entry.id)
    )
    db.flush()
