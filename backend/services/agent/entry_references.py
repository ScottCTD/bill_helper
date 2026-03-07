from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.models_finance import Entry
from backend.services.agent.change_contracts import EntrySelectorPayload
from backend.services.entries import normalize_tag_name

ENTRY_PUBLIC_ID_LENGTH = 8


def entry_public_id(entry_id: str, *, full: bool = False) -> str:
    normalized = str(entry_id)
    return normalized if full else normalized[:ENTRY_PUBLIC_ID_LENGTH]


def entry_to_public_record(entry: Entry, *, full_id: bool = False) -> dict[str, Any]:
    tag_names = sorted(normalize_tag_name(tag.name) for tag in entry.tags)
    return {
        "entry_id": entry_public_id(entry.id, full=full_id),
        "date": entry.occurred_at.isoformat(),
        "kind": entry.kind.value if hasattr(entry.kind, "value") else str(entry.kind),
        "name": entry.name,
        "amount_minor": entry.amount_minor,
        "currency_code": entry.currency_code,
        "from_entity": entry.from_entity,
        "to_entity": entry.to_entity,
        "tags": tag_names,
        "markdown_notes": entry.markdown_body,
    }


def entry_selector_from_entry(entry: Entry) -> dict[str, Any]:
    return {
        "date": entry.occurred_at.isoformat(),
        "amount_minor": entry.amount_minor,
        "from_entity": entry.from_entity,
        "to_entity": entry.to_entity,
        "name": entry.name,
    }


def entry_selector_to_json(selector: EntrySelectorPayload) -> dict[str, Any]:
    return {
        "date": selector.date.isoformat(),
        "amount_minor": selector.amount_minor,
        "from_entity": selector.from_entity,
        "to_entity": selector.to_entity,
        "name": selector.name,
    }


def find_entries_by_selector(db: Session, selector: EntrySelectorPayload) -> list[Entry]:
    return list(
        db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                Entry.occurred_at == selector.date,
                Entry.amount_minor == selector.amount_minor,
                func.lower(func.coalesce(Entry.name, "")) == selector.name.lower(),
                func.lower(func.coalesce(Entry.from_entity, "")) == selector.from_entity.lower(),
                func.lower(func.coalesce(Entry.to_entity, "")) == selector.to_entity.lower(),
            )
            .options(selectinload(Entry.tags))
            .order_by(Entry.created_at.asc())
        )
    )


def find_entries_by_id(db: Session, entry_id: str) -> list[Entry]:
    normalized = entry_id.strip().lower()
    if not normalized:
        return []

    exact_matches = list(
        db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                func.lower(Entry.id) == normalized,
            )
            .options(selectinload(Entry.tags))
            .order_by(Entry.created_at.asc())
        )
    )
    if exact_matches:
        return exact_matches

    return list(
        db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                func.lower(Entry.id).like(f"{normalized}%"),
            )
            .options(selectinload(Entry.tags))
            .order_by(Entry.created_at.asc())
        )
    )


def entry_id_ambiguity_details(entries: list[Entry], *, entry_id: str) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "candidate_count": len(entries),
        "candidate_entry_ids": [entry.id for entry in entries],
        "candidates": [entry_to_public_record(entry, full_id=True) for entry in entries],
    }


def entry_public_summary(entry: Entry) -> str:
    return (
        f"{entry_public_id(entry.id)} {entry.occurred_at.isoformat()} {entry.name} "
        f"{entry.amount_minor} {entry.currency_code} from={entry.from_entity or '-'} "
        f"to={entry.to_entity or '-'}"
    )
