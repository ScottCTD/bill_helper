from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.enums_agent import AgentChangeStatus, AgentChangeType, AgentReviewActionType
from backend.models_agent import AgentChangeItem, AgentReviewAction, AgentRun
from backend.services.agent.change_apply import apply_change_item_payload
from backend.services.agent.tool_handlers_propose import normalize_payload_for_change_type
from backend.services.agent.tool_types import ToolContext
from backend.services.entities import find_entity_by_name, normalize_entity_name


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_change_item_or_none(db: Session, item_id: str) -> AgentChangeItem | None:
    return db.scalar(
        select(AgentChangeItem)
        .where(AgentChangeItem.id == item_id)
        .options(selectinload(AgentChangeItem.review_actions))
    )


def _summarize_payload_override_diff(base_payload: dict[str, Any], override_payload: dict[str, Any]) -> str:
    def _is_record(value: Any) -> bool:
        return isinstance(value, dict)

    def _format_value(value: Any) -> str:
        if isinstance(value, str):
            return repr(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return repr(value)
        if isinstance(value, list):
            preview = ", ".join(_format_value(item) for item in value[:4])
            if len(value) > 4:
                preview = f"{preview}, ... (+{len(value) - 4} more)"
            return f"[{preview}]"
        if isinstance(value, dict):
            return "{...}"
        return repr(value)

    def _walk_differences(
        base_value: Any,
        override_value: Any,
        *,
        path: str,
        output: list[str],
    ) -> None:
        if base_value == override_value:
            return

        if _is_record(base_value) and _is_record(override_value):
            keys = sorted(set(base_value) | set(override_value))
            for key in keys:
                next_path = f"{path}.{key}" if path else key
                _walk_differences(base_value.get(key), override_value.get(key), path=next_path, output=output)
            return

        output.append(f"{path}={_format_value(override_value)}")

    changed_values: list[str] = []
    _walk_differences(base_payload, override_payload, path="", output=changed_values)
    if not changed_values:
        return ""
    if len(changed_values) <= 8:
        return "; ".join(changed_values)
    return f"{'; '.join(changed_values[:8])}; ... (+{len(changed_values) - 8} more)"


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


def _thread_id_for_change_item(db: Session, item: AgentChangeItem) -> str | None:
    return db.scalar(select(AgentRun.thread_id).where(AgentRun.id == item.run_id))


def _pending_change_items_for_thread(
    db: Session,
    *,
    thread_id: str,
    exclude_item_ids: set[str] | None = None,
) -> list[AgentChangeItem]:
    excluded = exclude_item_ids or set()
    items = list(
        db.scalars(
            select(AgentChangeItem)
            .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
            .where(
                AgentRun.thread_id == thread_id,
                AgentChangeItem.status == AgentChangeStatus.PENDING_REVIEW,
            )
            .order_by(AgentChangeItem.created_at.asc())
        )
    )
    if not excluded:
        return items
    return [item for item in items if item.id not in excluded]


def _normalized_entity_reference(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = normalize_entity_name(value)
    if not normalized:
        return None
    return normalized.lower()


def _entry_entity_labels_for_payload(
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
) -> dict[str, str]:
    raw_refs: list[Any] = []
    if change_type == AgentChangeType.CREATE_ENTRY:
        raw_refs = [payload.get("from_entity"), payload.get("to_entity")]
    elif change_type == AgentChangeType.UPDATE_ENTRY:
        patch = payload.get("patch")
        if isinstance(patch, dict):
            raw_refs = [patch.get("from_entity"), patch.get("to_entity")]

    labels: dict[str, str] = {}
    for raw_ref in raw_refs:
        normalized = _normalized_entity_reference(raw_ref)
        if normalized is None:
            continue
        labels.setdefault(normalized, normalize_entity_name(str(raw_ref)))
    return labels


def _pending_create_entity_root_names(
    pending_items: list[AgentChangeItem],
    *,
    exclude_item_ids: set[str] | None = None,
) -> set[str]:
    excluded = exclude_item_ids or set()
    names: set[str] = set()
    for item in pending_items:
        if item.id in excluded or item.change_type not in {
            AgentChangeType.CREATE_ENTITY,
            AgentChangeType.CREATE_ACCOUNT,
        }:
            continue
        raw_name = item.payload_json.get("name")
        normalized = _normalized_entity_reference(raw_name)
        if normalized is not None:
            names.add(normalized)
    return names


def _validate_entry_dependencies_ready_for_approval(
    db: Session,
    *,
    item: AgentChangeItem,
    payload: dict[str, Any],
) -> None:
    if item.change_type not in {AgentChangeType.CREATE_ENTRY, AgentChangeType.UPDATE_ENTRY}:
        return

    entity_labels = _entry_entity_labels_for_payload(change_type=item.change_type, payload=payload)
    if not entity_labels:
        return

    thread_id = _thread_id_for_change_item(db, item)
    if thread_id is None:
        return

    pending_items = _pending_change_items_for_thread(
        db,
        thread_id=thread_id,
        exclude_item_ids={item.id},
    )
    pending_entity_names = _pending_create_entity_root_names(pending_items)

    pending_blockers: list[str] = []
    missing_entities: list[str] = []
    for normalized_name, display_name in sorted(entity_labels.items()):
        if find_entity_by_name(db, display_name) is not None:
            continue
        if normalized_name in pending_entity_names:
            pending_blockers.append(display_name)
            continue
        missing_entities.append(display_name)

    if pending_blockers:
        quoted = ", ".join(f"'{name}'" for name in pending_blockers)
        noun = "create proposal" if len(pending_blockers) == 1 else "create proposals"
        raise ValueError(
            f"Entry depends on pending {noun} for {quoted}. Approve or reject those proposals first."
        )
    if missing_entities:
        quoted = ", ".join(f"'{name}'" for name in missing_entities)
        noun = "entity" if len(missing_entities) == 1 else "entities"
        raise ValueError(
            f"Entry references missing {noun} {quoted}. Propose and approve create_entity or create_account first."
        )


def _group_dependency_proposal_ids(payload: dict[str, Any]) -> list[str]:
    dependency_ids: list[str] = []
    for key in ("group_ref", "entry_ref", "child_group_ref"):
        value = payload.get(key)
        if not isinstance(value, dict):
            continue
        for proposal_key in ("create_group_proposal_id", "create_entry_proposal_id"):
            raw = value.get(proposal_key)
            if isinstance(raw, str) and raw:
                dependency_ids.append(raw)
    return dependency_ids


def _validate_group_dependencies_ready_for_approval(
    db: Session,
    *,
    item: AgentChangeItem,
    payload: dict[str, Any],
) -> None:
    if item.change_type != AgentChangeType.CREATE_GROUP_MEMBER:
        return

    dependency_ids = _group_dependency_proposal_ids(payload)
    if not dependency_ids:
        return

    pending_blockers: list[str] = []
    failed_blockers: list[str] = []
    missing_blockers: list[str] = []
    for dependency_id in dependency_ids:
        dependency_item = _get_change_item_or_none(db, dependency_id)
        if dependency_item is None:
            missing_blockers.append(dependency_id)
            continue
        if dependency_item.status in {AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED}:
            pending_blockers.append(dependency_id[:8])
            continue
        if dependency_item.status in {AgentChangeStatus.REJECTED, AgentChangeStatus.APPLY_FAILED}:
            failed_blockers.append(f"{dependency_id[:8]}:{dependency_item.status.value}")

    if pending_blockers:
        raise ValueError(
            "Group proposal depends on pending create proposals. Approve and apply those proposals first: "
            + ", ".join(sorted(pending_blockers))
        )
    if failed_blockers:
        raise ValueError(
            "Group proposal depends on rejected or failed create proposals and cannot be approved until edited or removed: "
            + ", ".join(sorted(failed_blockers))
        )
    if missing_blockers:
        raise ValueError(
            "Group proposal references missing proposal dependencies: " + ", ".join(sorted(missing_blockers))
        )


EDITABLE_CHANGE_TYPES = {
    AgentChangeType.CREATE_TAG,
    AgentChangeType.UPDATE_TAG,
    AgentChangeType.CREATE_ENTITY,
    AgentChangeType.UPDATE_ENTITY,
    AgentChangeType.CREATE_ACCOUNT,
    AgentChangeType.UPDATE_ACCOUNT,
    AgentChangeType.CREATE_ENTRY,
    AgentChangeType.UPDATE_ENTRY,
    AgentChangeType.CREATE_GROUP,
    AgentChangeType.UPDATE_GROUP,
    AgentChangeType.CREATE_GROUP_MEMBER,
}


def _validate_payload_override_supported(item: AgentChangeItem, payload_override: dict[str, Any] | None) -> None:
    if payload_override is None:
        return
    if item.change_type not in EDITABLE_CHANGE_TYPES:
        raise ValueError(
            "payload_override is only supported for editable create/update entry, tag, entity, account, and group items"
        )


def _normalized_payload_override(
    db: Session,
    *,
    item: AgentChangeItem,
    payload_override: dict[str, Any] | None,
) -> dict[str, Any]:
    _validate_payload_override_supported(item, payload_override)
    if payload_override is None:
        return item.payload_json
    return normalize_payload_for_change_type(
        ToolContext(db=db, run_id=item.run_id),
        change_type=item.change_type,
        payload=payload_override,
    )


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
    if item.status == AgentChangeStatus.APPLIED:
        raise ValueError("Applied items cannot be approved again")

    payload = _normalized_payload_override(db, item=item, payload_override=payload_override)
    override_note = None
    if payload_override is not None:
        diff_summary = _summarize_payload_override_diff(item.payload_json, payload_override)
        if diff_summary:
            override_note = f"payload_override: {diff_summary}"
    combined_note = _combine_notes(note, override_note)
    _validate_entry_dependencies_ready_for_approval(db, item=item, payload=payload)
    _validate_group_dependencies_ready_for_approval(db, item=item, payload=payload)

    approval_action = AgentReviewAction(
        change_item_id=item.id,
        action=AgentReviewActionType.APPROVE,
        actor=actor,
        note=combined_note,
    )
    db.add(approval_action)
    if payload_override is not None:
        item.payload_json = payload
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


def reject_change_item(
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
    if item.status == AgentChangeStatus.APPLIED:
        raise ValueError("Applied items cannot be changed back to rejected")

    payload = _normalized_payload_override(db, item=item, payload_override=payload_override)
    override_note = None
    if payload_override is not None:
        diff_summary = _summarize_payload_override_diff(item.payload_json, payload_override)
        if diff_summary:
            override_note = f"payload_override: {diff_summary}"
    combined_note = _combine_notes(note, override_note)

    action = AgentReviewAction(
        change_item_id=item.id,
        action=AgentReviewActionType.REJECT,
        actor=actor,
        note=combined_note,
    )
    item.payload_json = payload
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
    payload_override: dict[str, Any] | None = None,
) -> AgentChangeItem | None:
    item = _get_change_item_or_none(db, item_id)
    if item is None:
        return None
    if item.status == AgentChangeStatus.APPLIED:
        raise ValueError("Applied items cannot be reopened")

    payload = _normalized_payload_override(db, item=item, payload_override=payload_override)
    override_note = None
    if payload_override is not None:
        diff_summary = _summarize_payload_override_diff(item.payload_json, payload_override)
        if diff_summary:
            override_note = f"payload_override: {diff_summary}"
    combined_note = _combine_notes(note, override_note)
    item.payload_json = payload
    item.status = AgentChangeStatus.PENDING_REVIEW
    item.review_note = combined_note
    item.updated_at = utc_now()
    db.add(item)
    db.commit()
    db.refresh(item)
    db.refresh(item, attribute_names=["review_actions"])
    return item
