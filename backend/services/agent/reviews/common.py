from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models_agent import AgentChangeItem, AgentRun


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_change_item_or_none(db: Session, item_id: str) -> AgentChangeItem | None:
    return db.scalar(
        select(AgentChangeItem)
        .where(AgentChangeItem.id == item_id)
        .options(selectinload(AgentChangeItem.review_actions))
    )


def thread_id_for_change_item(db: Session, item: AgentChangeItem) -> str | None:
    return db.scalar(select(AgentRun.thread_id).where(AgentRun.id == item.run_id))


def combine_notes(note: str | None, extra: str | None) -> str | None:
    note_text = (note or "").strip()
    extra_text = (extra or "").strip()
    if note_text and extra_text:
        return f"{note_text} | {extra_text}"
    if note_text:
        return note_text
    if extra_text:
        return extra_text
    return None
