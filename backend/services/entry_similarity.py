from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.auth.contracts import RequestPrincipal
from backend.models_finance import Entry
from backend.schemas_finance import EntryKind, EntryTagSuggestionRequest
from backend.services.access_scope import entry_owner_filter

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_NOTES_MIN_TOKEN_LENGTH = 3
_MIN_SIMILARITY_SCORE = 0.35


@dataclass(slots=True, frozen=True)
class SimilarTaggedEntry:
    entry_id: str
    kind: EntryKind
    occurred_at: date
    updated_at: datetime
    name: str
    amount_minor: int
    currency_code: str
    from_entity: str | None
    to_entity: str | None
    markdown_body: str | None
    tags: list[str]


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip().lower()


def _tokenize(value: str | None, *, min_length: int = 1) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()
    return {token for token in _TOKEN_PATTERN.findall(normalized) if len(token) >= min_length}


def _ratio(left: str | None, right: str | None) -> float:
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def _token_overlap(left: str | None, right: str | None, *, min_length: int = 1) -> float:
    left_tokens = _tokenize(left, min_length=min_length)
    right_tokens = _tokenize(right, min_length=min_length)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _entity_match_score(
    *,
    draft_entity_id: str | None,
    draft_entity_name: str | None,
    candidate_entity_id: str | None,
    candidate_entity_name: str | None,
) -> float:
    if draft_entity_id and candidate_entity_id and draft_entity_id == candidate_entity_id:
        return 2.4
    if _normalize_text(draft_entity_name) and _normalize_text(draft_entity_name) == _normalize_text(candidate_entity_name):
        return 2.0
    overlap = _token_overlap(draft_entity_name, candidate_entity_name)
    if overlap > 0:
        return overlap * 1.25
    return 0.0


def _name_score(draft: EntryTagSuggestionRequest, candidate: Entry) -> float:
    normalized_draft_name = _normalize_text(draft.name)
    normalized_candidate_name = _normalize_text(candidate.name)
    if not normalized_draft_name or not normalized_candidate_name:
        return 0.0
    if normalized_draft_name == normalized_candidate_name:
        return 4.5
    if normalized_draft_name in normalized_candidate_name or normalized_candidate_name in normalized_draft_name:
        return 3.2
    return (_ratio(draft.name, candidate.name) * 2.4) + (_token_overlap(draft.name, candidate.name) * 1.8)


def _amount_score(draft_amount_minor: int | None, candidate_amount_minor: int) -> float:
    if draft_amount_minor is None or draft_amount_minor <= 0 or candidate_amount_minor <= 0:
        return 0.0
    if draft_amount_minor == candidate_amount_minor:
        return 1.8
    larger = max(draft_amount_minor, candidate_amount_minor)
    smaller = min(draft_amount_minor, candidate_amount_minor)
    ratio = smaller / larger
    if ratio >= 0.95:
        return 1.2
    if ratio >= 0.8:
        return 0.8
    if ratio >= 0.6:
        return 0.35
    return 0.0


def _candidate_score(draft: EntryTagSuggestionRequest, candidate: Entry) -> float:
    score = 0.0
    score += _name_score(draft, candidate)
    score += _entity_match_score(
        draft_entity_id=draft.from_entity_id,
        draft_entity_name=draft.from_entity,
        candidate_entity_id=candidate.from_entity_id,
        candidate_entity_name=candidate.from_entity,
    )
    score += _entity_match_score(
        draft_entity_id=draft.to_entity_id,
        draft_entity_name=draft.to_entity,
        candidate_entity_id=candidate.to_entity_id,
        candidate_entity_name=candidate.to_entity,
    )
    if draft.currency_code == candidate.currency_code:
        score += 0.9
    score += _amount_score(draft.amount_minor, candidate.amount_minor)
    score += _token_overlap(
        draft.markdown_body,
        candidate.markdown_body,
        min_length=_NOTES_MIN_TOKEN_LENGTH,
    ) * 0.75
    return score


def list_similar_tagged_entries(
    db: Session,
    *,
    principal: RequestPrincipal,
    draft: EntryTagSuggestionRequest,
    limit: int = 9,
) -> list[SimilarTaggedEntry]:
    stmt = (
        select(Entry)
        .join(Entry.tags)
        .where(
            Entry.is_deleted.is_(False),
            entry_owner_filter(principal),
        )
        .options(selectinload(Entry.tags))
        .distinct()
    )
    if draft.entry_id:
        stmt = stmt.where(Entry.id != draft.entry_id)

    candidates = list(db.scalars(stmt))
    same_kind: list[tuple[float, Entry]] = []
    cross_kind: list[tuple[float, Entry]] = []

    for candidate in candidates:
        if not candidate.tags:
            continue
        score = _candidate_score(draft, candidate)
        if score < _MIN_SIMILARITY_SCORE:
            continue
        bucket = same_kind if candidate.kind == draft.kind else cross_kind
        bucket.append((score, candidate))

    def sort_key(item: tuple[float, Entry]) -> tuple[float, int, float]:
        score, candidate = item
        return (
            score,
            candidate.occurred_at.toordinal(),
            candidate.updated_at.timestamp(),
        )

    ranked_candidates = sorted(same_kind, key=sort_key, reverse=True)[:limit]
    if len(ranked_candidates) < limit:
        ranked_candidates.extend(sorted(cross_kind, key=sort_key, reverse=True)[: limit - len(ranked_candidates)])

    return [
        SimilarTaggedEntry(
            entry_id=candidate.id,
            kind=candidate.kind,
            occurred_at=candidate.occurred_at,
            updated_at=candidate.updated_at,
            name=candidate.name,
            amount_minor=candidate.amount_minor,
            currency_code=candidate.currency_code,
            from_entity=candidate.from_entity,
            to_entity=candidate.to_entity,
            markdown_body=candidate.markdown_body,
            tags=[tag.name for tag in candidate.tags],
        )
        for _, candidate in ranked_candidates
    ]
