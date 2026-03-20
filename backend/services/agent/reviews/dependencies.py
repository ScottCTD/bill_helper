# CALLING SPEC:
# - Purpose: implement focused service logic for `dependencies`.
# - Inputs: callers that import `backend/services/agent/reviews/dependencies.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `dependencies`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.models_agent import AgentChangeItem, AgentRun
from backend.services.agent.change_contracts import ChangePayloadModel, parse_change_payload
from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload,
    CreateEntityPayload,
    CreateTagPayload,
)
from backend.services.agent.change_contracts.entries import CreateEntryPayload, UpdateEntryPayload
from backend.services.agent.change_contracts.groups import (
    ChildGroupMemberTargetPayload,
    CreateGroupMemberPayload,
    EntryGroupMemberTargetPayload,
)
from backend.services.agent.principal_scope import load_change_item_principal
from backend.services.agent.reviews.common import get_change_item_or_none, thread_id_for_change_item
from backend.services.entities import find_entity_by_name
from backend.services.crud_policy import PolicyViolation
from backend.services.tags import find_tag_by_name
from backend.validation.finance_names import normalize_entity_name, normalize_tag_name


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


def _thread_change_items_with_statuses(
    db: Session,
    *,
    thread_id: str,
    change_types: set[AgentChangeType],
    statuses: set[AgentChangeStatus],
) -> list[AgentChangeItem]:
    return list(
        db.scalars(
            select(AgentChangeItem)
            .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
            .where(
                AgentRun.thread_id == thread_id,
                AgentChangeItem.change_type.in_(change_types),
                AgentChangeItem.status.in_(statuses),
            )
            .order_by(AgentChangeItem.created_at.asc())
        )
    )


def _rejected_or_failed_create_entity_root_names(
    db: Session,
    *,
    thread_id: str,
) -> set[str]:
    names: set[str] = set()
    for item in _thread_change_items_with_statuses(
        db,
        thread_id=thread_id,
        change_types={AgentChangeType.CREATE_ENTITY, AgentChangeType.CREATE_ACCOUNT},
        statuses={AgentChangeStatus.REJECTED, AgentChangeStatus.APPLY_FAILED},
    ):
        parsed = parse_change_payload(item.change_type, item.payload_json)
        if not isinstance(parsed, CreateEntityPayload | CreateAccountPayload):
            continue
        normalized = _normalized_entity_reference(parsed.name)
        if normalized is not None:
            names.add(normalized)
    return names


def _rejected_or_failed_create_tag_names(
    db: Session,
    *,
    thread_id: str,
) -> set[str]:
    names: set[str] = set()
    for item in _thread_change_items_with_statuses(
        db,
        thread_id=thread_id,
        change_types={AgentChangeType.CREATE_TAG},
        statuses={AgentChangeStatus.REJECTED, AgentChangeStatus.APPLY_FAILED},
    ):
        parsed = parse_change_payload(item.change_type, item.payload_json)
        if not isinstance(parsed, CreateTagPayload):
            continue
        normalized = normalize_tag_name(parsed.name)
        if normalized:
            names.add(normalized)
    return names


def _normalized_entity_reference(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = normalize_entity_name(value)
    if not normalized:
        return None
    return normalized.lower()


def _entry_entity_labels_for_payload(
    payload: CreateEntryPayload | UpdateEntryPayload,
) -> dict[str, str]:
    raw_refs: list[str | None]
    if isinstance(payload, CreateEntryPayload):
        raw_refs = [payload.from_entity, payload.to_entity]
    else:
        raw_refs = []
        if "from_entity" in payload.patch.model_fields_set:
            raw_refs.append(payload.patch.from_entity)
        if "to_entity" in payload.patch.model_fields_set:
            raw_refs.append(payload.patch.to_entity)

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
        parsed = parse_change_payload(item.change_type, item.payload_json)
        if not isinstance(parsed, CreateEntityPayload | CreateAccountPayload):
            continue
        normalized = _normalized_entity_reference(parsed.name)
        if normalized is not None:
            names.add(normalized)
    return names


def _entry_tag_labels_for_payload(
    payload: CreateEntryPayload | UpdateEntryPayload,
) -> dict[str, str]:
    raw_tags: list[str]
    if isinstance(payload, CreateEntryPayload):
        raw_tags = list(payload.tags)
    else:
        if "tags" not in payload.patch.model_fields_set or payload.patch.tags is None:
            return {}
        raw_tags = list(payload.patch.tags)

    labels: dict[str, str] = {}
    for raw in raw_tags:
        normalized = normalize_tag_name(str(raw))
        if not normalized:
            continue
        labels.setdefault(normalized, str(raw).strip())
    return labels


def _pending_create_tag_names(
    pending_items: list[AgentChangeItem],
    *,
    exclude_item_ids: set[str] | None = None,
) -> set[str]:
    excluded = exclude_item_ids or set()
    names: set[str] = set()
    for item in pending_items:
        if item.id in excluded or item.change_type != AgentChangeType.CREATE_TAG:
            continue
        parsed = parse_change_payload(item.change_type, item.payload_json)
        if not isinstance(parsed, CreateTagPayload):
            continue
        normalized = normalize_tag_name(parsed.name)
        if normalized:
            names.add(normalized)
    return names


def validate_entry_dependencies_ready_for_approval(
    db: Session,
    *,
    item: AgentChangeItem,
    payload: ChangePayloadModel,
) -> None:
    if item.change_type not in {AgentChangeType.CREATE_ENTRY, AgentChangeType.UPDATE_ENTRY}:
        return
    if not isinstance(payload, CreateEntryPayload | UpdateEntryPayload):
        raise RuntimeError(f"Unexpected payload model for change type {item.change_type.value}")

    thread_id = thread_id_for_change_item(db, item)
    if thread_id is None:
        return

    pending_items = _pending_change_items_for_thread(
        db,
        thread_id=thread_id,
        exclude_item_ids={item.id},
    )
    owner_principal = load_change_item_principal(db, item_id=item.id)
    if owner_principal is None:
        return

    entity_labels = _entry_entity_labels_for_payload(payload)
    if entity_labels:
        pending_entity_names = _pending_create_entity_root_names(pending_items)
        rejected_entity_names = _rejected_or_failed_create_entity_root_names(db, thread_id=thread_id)
        pending_blockers: list[str] = []
        rejected_entity_blockers: list[str] = []
        missing_entities: list[str] = []
        for normalized_name, display_name in sorted(entity_labels.items()):
            if find_entity_by_name(db, display_name, owner_user_id=owner_principal.user_id) is not None:
                continue
            if normalized_name in pending_entity_names:
                pending_blockers.append(display_name)
                continue
            if normalized_name in rejected_entity_names:
                rejected_entity_blockers.append(display_name)
                continue
            missing_entities.append(display_name)

        if pending_blockers:
            quoted = ", ".join(f"'{name}'" for name in pending_blockers)
            noun = "create proposal" if len(pending_blockers) == 1 else "create proposals"
            raise PolicyViolation.unprocessable_content(
                f"Entry depends on pending {noun} for {quoted}. Approve or reject those proposals first."
            )
        if rejected_entity_blockers:
            quoted = ", ".join(f"'{name}'" for name in rejected_entity_blockers)
            raise PolicyViolation.unprocessable_content(
                f"Entry depends on entity name(s) {quoted} with rejected or failed create_entity or create_account proposals in this thread. "
                "Edit the entry or reopen a create proposal before approving."
            )
        if missing_entities:
            quoted = ", ".join(f"'{name}'" for name in missing_entities)
            noun = "entity" if len(missing_entities) == 1 else "entities"
            raise PolicyViolation.unprocessable_content(
                f"Entry references missing {noun} {quoted}. Propose and approve create_entity or create_account first."
            )

    tag_labels = _entry_tag_labels_for_payload(payload)
    if not tag_labels:
        return

    pending_tag_names = _pending_create_tag_names(pending_items)
    rejected_tag_names = _rejected_or_failed_create_tag_names(db, thread_id=thread_id)
    tag_pending_blockers: list[str] = []
    tag_rejected_blockers: list[str] = []
    for normalized_name, display_name in sorted(tag_labels.items()):
        if find_tag_by_name(db, display_name, owner_user_id=owner_principal.user_id) is not None:
            continue
        if normalized_name in pending_tag_names:
            tag_pending_blockers.append(display_name)
            continue
        if normalized_name in rejected_tag_names:
            tag_rejected_blockers.append(display_name)

    if tag_pending_blockers:
        quoted = ", ".join(f"'{name}'" for name in tag_pending_blockers)
        noun = "create_tag proposal" if len(tag_pending_blockers) == 1 else "create_tag proposals"
        raise PolicyViolation.unprocessable_content(
            f"Entry depends on pending {noun} for {quoted}. Approve or reject those proposals first."
        )
    if tag_rejected_blockers:
        quoted = ", ".join(f"'{name}'" for name in tag_rejected_blockers)
        raise PolicyViolation.unprocessable_content(
            f"Entry references tag(s) {quoted} with rejected or failed create_tag proposals in this thread. "
            "Remove those tags from the entry or reopen a create_tag proposal before approving."
        )


def _group_dependency_proposal_ids(payload: CreateGroupMemberPayload) -> list[str]:
    dependency_ids: list[str] = []
    references = [payload.group_ref.create_group_proposal_id]
    if isinstance(payload.target, EntryGroupMemberTargetPayload):
        references.append(payload.target.entry_ref.create_entry_proposal_id)
    elif isinstance(payload.target, ChildGroupMemberTargetPayload):
        references.append(payload.target.group_ref.create_group_proposal_id)
    for proposal_id in references:
        if proposal_id:
            dependency_ids.append(proposal_id)
    return dependency_ids


def validate_group_dependencies_ready_for_approval(
    db: Session,
    *,
    item: AgentChangeItem,
    payload: ChangePayloadModel,
) -> None:
    if item.change_type != AgentChangeType.CREATE_GROUP_MEMBER:
        return
    if not isinstance(payload, CreateGroupMemberPayload):
        raise RuntimeError(f"Unexpected payload model for change type {item.change_type.value}")

    dependency_ids = _group_dependency_proposal_ids(payload)
    if not dependency_ids:
        return

    pending_blockers: list[str] = []
    failed_blockers: list[str] = []
    missing_blockers: list[str] = []
    for dependency_id in dependency_ids:
        dependency_item = get_change_item_or_none(db, dependency_id)
        if dependency_item is None:
            missing_blockers.append(dependency_id)
            continue
        if dependency_item.status in {AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED}:
            pending_blockers.append(dependency_id[:8])
            continue
        if dependency_item.status in {AgentChangeStatus.REJECTED, AgentChangeStatus.APPLY_FAILED}:
            failed_blockers.append(f"{dependency_id[:8]}:{dependency_item.status.value}")

    if pending_blockers:
        raise PolicyViolation.unprocessable_content(
            "Group proposal depends on pending create proposals. Approve and apply those proposals first: "
            + ", ".join(sorted(pending_blockers))
        )
    if failed_blockers:
        raise PolicyViolation.unprocessable_content(
            "Group proposal depends on rejected or failed create proposals and cannot be approved until edited or removed: "
            + ", ".join(sorted(failed_blockers))
        )
    if missing_blockers:
        raise PolicyViolation.unprocessable_content(
            "Group proposal references missing proposal dependencies: " + ", ".join(sorted(missing_blockers))
        )
