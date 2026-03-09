from __future__ import annotations

from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.models_finance import Entry
from backend.services.agent.change_contracts import EntrySelectorPayload
from backend.validation.finance_names import normalize_tag_name

ENTRY_PUBLIC_ID_LENGTH = 8


class EntryPublicRecord(TypedDict):
    entry_id: str
    date: str
    kind: str
    name: str
    amount_minor: int
    currency_code: str
    from_entity: str | None
    to_entity: str | None
    tags: list[str]
    markdown_notes: str | None


class EntrySelectorRecord(TypedDict):
    date: str
    amount_minor: int
    from_entity: str | None
    to_entity: str | None
    name: str


class EntryIdAmbiguityDetails(TypedDict):
    entry_id: str
    candidate_count: int
    candidate_entry_ids: list[str]
    candidates: list[EntryPublicRecord]


def entry_public_id(entry_id: str, *, full: bool = False) -> str:
    normalized = str(entry_id)
    return normalized if full else normalized[:ENTRY_PUBLIC_ID_LENGTH]


def entry_to_public_record(entry: Entry, *, full_id: bool = False) -> EntryPublicRecord:
    tag_names = sorted(normalize_tag_name(tag.name) for tag in entry.tags)
    return {
        "entry_id": entry_public_id(entry.id, full=full_id),
        "date": entry.occurred_at.isoformat(),
        "kind": entry.kind.value if hasattr(entry.kind, "value") else str(entry.kind),
        "name": entry.name,
        "amount_minor": entry.amount_minor,
        "currency_code": entry.currency_code,
        "from_entity": _effective_entry_entity_name(entry, side="from"),
        "to_entity": _effective_entry_entity_name(entry, side="to"),
        "tags": tag_names,
        "markdown_notes": entry.markdown_body,
    }


def entry_selector_from_entry(entry: Entry) -> EntrySelectorRecord:
    return {
        "date": entry.occurred_at.isoformat(),
        "amount_minor": entry.amount_minor,
        "from_entity": _effective_entry_entity_name(entry, side="from"),
        "to_entity": _effective_entry_entity_name(entry, side="to"),
        "name": entry.name,
    }


def _effective_entry_entity_name(entry: Entry, *, side: str) -> str | None:
    if side == "from":
        if entry.from_entity:
            return entry.from_entity
        return entry.from_entity_ref.name if entry.from_entity_ref is not None else None
    if side == "to":
        if entry.to_entity:
            return entry.to_entity
        return entry.to_entity_ref.name if entry.to_entity_ref is not None else None
    raise ValueError(f"Unsupported entry entity side: {side}")


def entry_selector_to_json(selector: EntrySelectorPayload) -> EntrySelectorRecord:
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


def find_entries_by_exact_id(db: Session, entry_id: str) -> list[Entry]:
    normalized = entry_id.strip().lower()
    if not normalized:
        return []
    return list(
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


def find_entries_by_public_id_prefix(db: Session, entry_id_prefix: str) -> list[Entry]:
    normalized = entry_id_prefix.strip().lower()
    if not normalized:
        return []
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


def entry_id_ambiguity_details(entries: list[Entry], *, entry_id: str) -> EntryIdAmbiguityDetails:
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
