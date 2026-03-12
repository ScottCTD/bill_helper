from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.models_agent import AgentChangeItem, AgentRun
from backend.services.agent.change_contracts import ChangePayloadModel, parse_change_payload
from backend.services.agent.change_contracts.catalog import CreateAccountPayload, CreateEntityPayload
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
from backend.validation.finance_names import normalize_entity_name


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

    entity_labels = _entry_entity_labels_for_payload(payload)
    if not entity_labels:
        return

    thread_id = thread_id_for_change_item(db, item)
    if thread_id is None:
        return

    pending_items = _pending_change_items_for_thread(
        db,
        thread_id=thread_id,
        exclude_item_ids={item.id},
    )
    pending_entity_names = _pending_create_entity_root_names(pending_items)
    owner_principal = load_change_item_principal(db, item_id=item.id)
    if owner_principal is None:
        return

    pending_blockers: list[str] = []
    missing_entities: list[str] = []
    for normalized_name, display_name in sorted(entity_labels.items()):
        if find_entity_by_name(db, display_name, owner_user_id=owner_principal.user_id) is not None:
            continue
        if normalized_name in pending_entity_names:
            pending_blockers.append(display_name)
            continue
        missing_entities.append(display_name)

    if pending_blockers:
        quoted = ", ".join(f"'{name}'" for name in pending_blockers)
        noun = "create proposal" if len(pending_blockers) == 1 else "create proposals"
        raise PolicyViolation.unprocessable_content(
            f"Entry depends on pending {noun} for {quoted}. Approve or reject those proposals first."
        )
    if missing_entities:
        quoted = ", ".join(f"'{name}'" for name in missing_entities)
        noun = "entity" if len(missing_entities) == 1 else "entities"
        raise PolicyViolation.unprocessable_content(
            f"Entry references missing {noun} {quoted}. Propose and approve create_entity or create_account first."
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
