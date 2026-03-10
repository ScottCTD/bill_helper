from __future__ import annotations

from sqlalchemy.orm import Session

from backend.enums_agent import AgentChangeStatus, AgentReviewActionType
from backend.models_agent import AgentChangeItem, AgentReviewAction
from backend.services.agent.apply.dispatch import apply_change_item_payload
from backend.services.agent.reviews.common import combine_notes, get_change_item_or_none, utc_now
from backend.services.agent.reviews.dependencies import (
    validate_entry_dependencies_ready_for_approval,
    validate_group_dependencies_ready_for_approval,
)
from backend.services.agent.reviews.overrides import (
    normalized_payload_override,
    summarize_payload_override_diff,
)
from backend.services.crud_policy import PolicyViolation


def approve_change_item(
    db: Session,
    *,
    item_id: str,
    actor: str,
    note: str | None = None,
    payload_override: dict[str, object] | None = None,
) -> AgentChangeItem | None:
    item = get_change_item_or_none(db, item_id)
    if item is None:
        return None
    if item.status == AgentChangeStatus.APPLIED:
        raise PolicyViolation.conflict("Applied items cannot be approved again")

    payload_json, payload = normalized_payload_override(db, item=item, payload_override=payload_override)
    override_note = None
    if payload_override is not None:
        diff_summary = summarize_payload_override_diff(item.payload_json, payload_override)
        if diff_summary:
            override_note = f"payload_override: {diff_summary}"
    combined_note = combine_notes(note, override_note)
    validate_entry_dependencies_ready_for_approval(db, item=item, payload=payload)
    validate_group_dependencies_ready_for_approval(db, item=item, payload=payload)

    approval_action = AgentReviewAction(
        change_item_id=item.id,
        action=AgentReviewActionType.APPROVE,
        actor=actor,
        note=combined_note,
    )
    db.add(approval_action)
    if payload_override is not None:
        item.payload_json = payload_json
    item.status = AgentChangeStatus.APPROVED
    item.review_note = combined_note

    try:
        resource = apply_change_item_payload(
            db,
            change_type=item.change_type,
            payload=payload,
            actor_name=actor,
        )
    except Exception as exc:
        item.status = AgentChangeStatus.APPLY_FAILED
        reason = str(exc)
        item.review_note = combine_notes(combined_note, f"apply failed: {reason}")
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


def reject_change_item(
    db: Session,
    *,
    item_id: str,
    actor: str,
    note: str | None = None,
    payload_override: dict[str, object] | None = None,
) -> AgentChangeItem | None:
    item = get_change_item_or_none(db, item_id)
    if item is None:
        return None
    if item.status == AgentChangeStatus.APPLIED:
        raise PolicyViolation.conflict("Applied items cannot be changed back to rejected")

    payload_json, _ = normalized_payload_override(db, item=item, payload_override=payload_override)
    override_note = None
    if payload_override is not None:
        diff_summary = summarize_payload_override_diff(item.payload_json, payload_override)
        if diff_summary:
            override_note = f"payload_override: {diff_summary}"
    combined_note = combine_notes(note, override_note)

    action = AgentReviewAction(
        change_item_id=item.id,
        action=AgentReviewActionType.REJECT,
        actor=actor,
        note=combined_note,
    )
    item.payload_json = payload_json
    item.status = AgentChangeStatus.REJECTED
    item.review_note = combined_note
    item.updated_at = utc_now()
    db.add(action)
    db.add(item)
    db.commit()
    db.refresh(item)
    db.refresh(item, attribute_names=["review_actions"])
    return item


def reopen_change_item(
    db: Session,
    *,
    item_id: str,
    actor: str,
    note: str | None = None,
    payload_override: dict[str, object] | None = None,
) -> AgentChangeItem | None:
    item = get_change_item_or_none(db, item_id)
    if item is None:
        return None
    if item.status == AgentChangeStatus.APPLIED:
        raise PolicyViolation.conflict("Applied items cannot be reopened")

    payload_json, _ = normalized_payload_override(db, item=item, payload_override=payload_override)
    override_note = None
    if payload_override is not None:
        diff_summary = summarize_payload_override_diff(item.payload_json, payload_override)
        if diff_summary:
            override_note = f"payload_override: {diff_summary}"
    combined_note = combine_notes(note, override_note)
    item.payload_json = payload_json
    item.status = AgentChangeStatus.PENDING_REVIEW
    item.review_note = combined_note
    item.updated_at = utc_now()
    db.add(item)
    db.commit()
    db.refresh(item)
    db.refresh(item, attribute_names=["review_actions"])
    return item
