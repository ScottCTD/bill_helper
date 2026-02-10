from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.enums import AgentChangeStatus, AgentChangeType, AgentReviewActionType
from backend.models import AgentChangeItem, AgentReviewAction
from backend.services.agent.change_apply import apply_change_item_payload


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_change_item_or_none(db: Session, item_id: str) -> AgentChangeItem | None:
    return db.scalar(
        select(AgentChangeItem)
        .where(AgentChangeItem.id == item_id)
        .options(selectinload(AgentChangeItem.review_actions))
    )


def _summarize_payload_override_diff(base_payload: dict[str, Any], override_payload: dict[str, Any]) -> str:
    changed_keys = sorted(
        key
        for key in set(base_payload) | set(override_payload)
        if base_payload.get(key) != override_payload.get(key)
    )
    if not changed_keys:
        return ""
    if len(changed_keys) <= 8:
        return ", ".join(changed_keys)
    return f"{', '.join(changed_keys[:8])}, ... (+{len(changed_keys) - 8} more)"


def _combine_notes(note: str | None, extra: str | None) -> str | None:
    note_text = (note or "").strip()
    extra_text = (extra or "").strip()
    if note_text and extra_text:
        return f"{note_text} | {extra_text}"
    if note_text:
        return note_text
    if extra_text:
        return extra_text
    return None


def approve_change_item(
    db: Session,
    *,
    item_id: str,
    actor: str,
    note: str | None = None,
    payload_override: dict[str, Any] | None = None,
) -> AgentChangeItem | None:
    item = _get_change_item_or_none(db, item_id)
    if item is None:
        return None
    if item.status != AgentChangeStatus.PENDING_REVIEW:
        raise ValueError("Only PENDING_REVIEW items can be approved")

    if payload_override is not None and item.change_type not in {
        AgentChangeType.CREATE_ENTRY,
        AgentChangeType.UPDATE_ENTRY,
    }:
        raise ValueError("payload_override is only supported for create_entry/update_entry items")

    payload = payload_override if payload_override is not None else item.payload_json
    override_note = None
    if payload_override is not None:
        diff_summary = _summarize_payload_override_diff(item.payload_json, payload_override)
        if diff_summary:
            override_note = f"payload_override_diff: {diff_summary}"
    combined_note = _combine_notes(note, override_note)

    approval_action = AgentReviewAction(
        change_item_id=item.id,
        action=AgentReviewActionType.APPROVE,
        actor=actor,
        note=combined_note,
    )
    db.add(approval_action)
    item.status = AgentChangeStatus.APPROVED
    item.review_note = combined_note

    try:
        resource = apply_change_item_payload(
            db,
            change_type=item.change_type,
            payload=payload,
        )
    except Exception as exc:
        item.status = AgentChangeStatus.APPLY_FAILED
        reason = str(exc)
        item.review_note = _combine_notes(combined_note, f"apply failed: {reason}")
        item.updated_at = utc_now()
        db.add(item)
        db.commit()
        db.refresh(item)
        db.refresh(item, attribute_names=["review_actions"])
        raise

    item.status = AgentChangeStatus.APPLIED
    item.applied_resource_type = resource.resource_type
    item.applied_resource_id = resource.resource_id
    item.updated_at = utc_now()
    db.add(item)
    db.commit()
    db.refresh(item)
    db.refresh(item, attribute_names=["review_actions"])
    return item


def reject_change_item(db: Session, *, item_id: str, actor: str, note: str | None = None) -> AgentChangeItem | None:
    item = _get_change_item_or_none(db, item_id)
    if item is None:
        return None
    if item.status != AgentChangeStatus.PENDING_REVIEW:
        raise ValueError("Only PENDING_REVIEW items can be rejected")

    action = AgentReviewAction(
        change_item_id=item.id,
        action=AgentReviewActionType.REJECT,
        actor=actor,
        note=note,
    )
    item.status = AgentChangeStatus.REJECTED
    item.review_note = note
    item.updated_at = utc_now()
    db.add(action)
    db.add(item)
    db.commit()
    db.refresh(item)
    db.refresh(item, attribute_names=["review_actions"])
    return item
