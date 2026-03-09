from __future__ import annotations

from copy import deepcopy
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.enums_finance import EntryKind, GroupMemberRole, GroupType
from backend.models_finance import Account, AccountSnapshot, Entry, EntryGroup, EntryGroupMember, Tag
from backend.models_agent import AgentChangeItem, AgentRun
from backend.services.agent.change_contracts import (
    CreateGroupMemberPayload,
    CreateGroupPayload,
    DeleteGroupMemberPayload,
    DeleteGroupPayload,
    EntryReferencePayload,
    EntrySelectorPayload,
    GroupReferencePayload,
    UpdateGroupPayload,
    parse_change_payload as parse_change_payload_model,
    validate_patch_map_paths,
)
from backend.services.agent.entry_references import (
    entry_id_ambiguity_details,
    entry_public_id,
    entry_selector_from_entry,
    entry_selector_to_json,
    find_entries_by_id,
    find_entries_by_selector,
)
from backend.services.agent.group_references import (
    find_groups_by_id,
    group_detail_public_record,
    group_id_ambiguity_details,
    group_owner_condition,
    group_public_id,
)
from backend.services.agent.proposal_patching import apply_patch_map_to_payload
from backend.services.agent.proposal_metadata import proposal_metadata_for_change_type
from backend.services.agent.tool_args import (
    AccountPatchArgs,
    EntryPatchArgs,
    ProposeCreateAccountArgs,
    ProposeCreateEntityArgs,
    ProposeCreateEntryArgs,
    ProposeCreateGroupArgs,
    ProposeCreateTagArgs,
    ProposeDeleteAccountArgs,
    ProposeDeleteEntityArgs,
    ProposeDeleteEntryArgs,
    ProposeDeleteGroupArgs,
    ProposeDeleteTagArgs,
    ProposeUpdateAccountArgs,
    ProposeUpdateEntityArgs,
    ProposeUpdateEntryArgs,
    ProposeUpdateGroupArgs,
    ProposeUpdateGroupMembershipArgs,
    ProposeUpdateTagArgs,
    RemovePendingProposalArgs,
    UpdatePendingProposalArgs,
)
from backend.services.accounts import find_account_by_name
from backend.services.agent.tool_handlers_read import (
    entry_ambiguity_details,
    entry_to_public_record,
    error_result,
    format_lines,
)
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.services.entities import (
    ACCOUNT_CATEGORY_DETAIL,
    find_entity_by_name,
    is_account_entity,
    normalize_entity_category,
    normalize_entity_name,
)
from backend.services.groups import build_group_graph, build_group_summary, group_tree_options
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.taxonomy import get_single_term_name_map
from backend.services.users import ensure_current_user


def proposal_short_id(item_id: str) -> str:
    return item_id[:8]


def proposal_result(summary: str, *, preview: dict[str, Any], item: AgentChangeItem) -> ToolExecutionResult:
    output_json = {
        "status": "OK",
        "summary": summary,
        "item_status": item.status.value,
        "proposal_id": item.id,
        "proposal_short_id": proposal_short_id(item.id),
        "preview": preview,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: {summary}",
                f"status: {item.status.value}",
                f"proposal_id: {item.id}",
                f"proposal_short_id: {proposal_short_id(item.id)}",
                f"preview: {preview}",
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )


def account_payload_record(account: Account) -> dict[str, Any]:
    return {
        "name": account.name,
        "currency_code": account.currency_code,
        "is_active": account.is_active,
        "markdown_body": account.markdown_body,
    }


def create_change_item(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    rationale_text: str,
) -> AgentChangeItem:
    item = AgentChangeItem(
        run_id=context.run_id,
        change_type=change_type,
        payload_json=payload,
        rationale_text=rationale_text,
        status=AgentChangeStatus.PENDING_REVIEW,
    )
    context.db.add(item)
    context.db.flush()
    return item


def _reference_details(
    *,
    entry_id: str | None,
    selector: EntrySelectorPayload | None,
) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if entry_id is not None:
        details["entry_id"] = entry_id
    if selector is not None:
        details["selector"] = entry_selector_to_json(selector)
    return details


def _find_entries_for_reference(
    context: ToolContext,
    *,
    entry_id: str | None,
    selector: EntrySelectorPayload | None,
) -> list[Entry]:
    if entry_id is not None:
        return find_entries_by_id(context.db, entry_id)
    if selector is None:  # pragma: no cover - validated by Pydantic
        return []
    return find_entries_by_selector(context.db, selector)


def pending_proposals_for_thread(context: ToolContext) -> list[AgentChangeItem]:
    return proposals_for_thread(context, statuses={AgentChangeStatus.PENDING_REVIEW})


def proposals_for_thread(
    context: ToolContext,
    *,
    statuses: set[AgentChangeStatus] | None = None,
) -> list[AgentChangeItem]:
    thread_id = context.db.scalar(select(AgentRun.thread_id).where(AgentRun.id == context.run_id))
    if thread_id is None:
        return []
    conditions = [AgentRun.thread_id == thread_id]
    if statuses is not None:
        conditions.append(AgentChangeItem.status.in_(sorted(statuses, key=lambda value: value.value)))
    return list(
        context.db.scalars(
            select(AgentChangeItem)
            .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
            .where(*conditions)
            .order_by(AgentChangeItem.created_at.asc())
        )
    )


def normalized_pending_create_entity_root_names(
    context: ToolContext,
    *,
    exclude_item_id: str | None = None,
) -> set[str]:
    names: set[str] = set()
    for item in pending_proposals_for_thread(context):
        if exclude_item_id is not None and item.id == exclude_item_id:
            continue
        if item.change_type not in {
            AgentChangeType.CREATE_ENTITY,
            AgentChangeType.CREATE_ACCOUNT,
        }:
            continue
        raw_name = item.payload_json.get("name")
        if not isinstance(raw_name, str):
            continue
        normalized = normalize_entity_name(raw_name)
        if normalized:
            names.add(normalized.lower())
    return names


def has_pending_create_entity_root_proposal(
    context: ToolContext,
    entity_name: str,
    *,
    exclude_item_id: str | None = None,
) -> bool:
    normalized = normalize_entity_name(entity_name)
    if not normalized:
        return False
    return normalized.lower() in normalized_pending_create_entity_root_names(
        context,
        exclude_item_id=exclude_item_id,
    )


def validate_proposed_entity_reference(context: ToolContext, entity_name: str) -> None:
    if find_entity_by_name(context.db, entity_name) is not None:
        return
    if has_pending_create_entity_root_proposal(context, entity_name):
        return
    raise ValueError(
        f"entity not found: '{entity_name}'. Use an existing entity or propose_create_entity "
        "or propose_create_account for it in the current thread first."
    )


def validate_create_entry_entity_references(
    context: ToolContext,
    *,
    from_entity: str,
    to_entity: str,
) -> None:
    validate_proposed_entity_reference(context, from_entity)
    validate_proposed_entity_reference(context, to_entity)


def validate_update_entry_entity_patch(context: ToolContext, patch: EntryPatchArgs) -> None:
    if "from_entity" in patch.model_fields_set and patch.from_entity is not None:
        validate_proposed_entity_reference(context, patch.from_entity)
    if "to_entity" in patch.model_fields_set and patch.to_entity is not None:
        validate_proposed_entity_reference(context, patch.to_entity)


def resolve_pending_proposal_by_id(context: ToolContext, proposal_id: str) -> AgentChangeItem | None:
    return resolve_proposal_by_id(
        context,
        proposal_id,
        items=pending_proposals_for_thread(context),
        detail_label="pending proposals",
    )


def resolve_proposal_by_id(
    context: ToolContext,
    proposal_id: str,
    *,
    items: list[AgentChangeItem] | None = None,
    detail_label: str = "thread proposals",
) -> AgentChangeItem | None:
    proposal_items = proposals_for_thread(context) if items is None else items
    if not proposal_items:
        return None

    exact = next((item for item in proposal_items if item.id.lower() == proposal_id.lower()), None)
    if exact is not None:
        return exact

    matches = [item for item in proposal_items if item.id.lower().startswith(proposal_id.lower())]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        example_ids = [item.id[:8] for item in matches[:5]]
        raise ValueError(f"proposal_id '{proposal_id}' is ambiguous across {detail_label}: {example_ids}")
    return None


def runtime_current_user_id(context: ToolContext) -> str:
    settings = resolve_runtime_settings(context.db)
    current_user = ensure_current_user(context.db, settings.current_user_name)
    return current_user.id


def _find_groups_for_reference(context: ToolContext, *, group_id: str) -> list[EntryGroup]:
    return find_groups_by_id(
        context.db,
        group_id=group_id,
        owner_user_id=runtime_current_user_id(context),
    )


def _sorted_group_memberships(group: EntryGroup) -> list[EntryGroupMember]:
    return sorted(
        group.memberships,
        key=lambda member: (member.position, member.created_at, member.id),
    )


def _descendant_entries_for_group(group: EntryGroup) -> list[Entry]:
    entries: list[Entry] = []
    for membership in _sorted_group_memberships(group):
        if membership.entry is not None and not membership.entry.is_deleted:
            entries.append(membership.entry)
            continue
        if membership.child_group is None:
            continue
        for child_membership in _sorted_group_memberships(membership.child_group):
            if child_membership.entry is not None and not child_membership.entry.is_deleted:
                entries.append(child_membership.entry)
    return entries


def _group_preview_from_existing(group: EntryGroup) -> dict[str, Any]:
    summary = build_group_summary(group)
    return {
        "source": "group",
        "group_id": group.id,
        "group_short_id": group_public_id(group.id),
        "name": summary.name,
        "group_type": summary.group_type.value,
        "direct_member_count": summary.direct_member_count,
        "descendant_entry_count": summary.descendant_entry_count,
    }


def _group_preview_from_proposal(item: AgentChangeItem) -> dict[str, Any]:
    payload = item.payload_json
    return {
        "source": "proposal",
        "proposal_id": item.id,
        "proposal_short_id": proposal_short_id(item.id),
        "proposal_status": item.status.value,
        "name": payload.get("name"),
        "group_type": payload.get("group_type"),
    }


def _entry_preview_from_proposal(item: AgentChangeItem) -> dict[str, Any]:
    payload = item.payload_json
    return {
        "source": "proposal",
        "proposal_id": item.id,
        "proposal_short_id": proposal_short_id(item.id),
        "proposal_status": item.status.value,
        "entry_id": payload.get("entry_id"),
        "date": payload.get("date"),
        "kind": payload.get("kind"),
        "name": payload.get("name"),
        "amount_minor": payload.get("amount_minor"),
        "currency_code": payload.get("currency_code"),
        "from_entity": payload.get("from_entity"),
        "to_entity": payload.get("to_entity"),
        "tags": payload.get("tags") or [],
        "markdown_notes": payload.get("markdown_notes"),
    }


def _match_existing_group_or_error(
    context: ToolContext,
    *,
    group_id: str,
) -> EntryGroup | ToolExecutionResult:
    matches = _find_groups_for_reference(context, group_id=group_id)
    if not matches:
        return error_result("no group matched group_id", details={"group_id": group_id})
    if len(matches) > 1:
        return error_result(
            "ambiguous group_id matched multiple groups; retry with one of the candidate ids",
            details=group_id_ambiguity_details(matches, group_id=group_id),
        )
    return matches[0]


def _match_existing_entry_or_error(
    context: ToolContext,
    *,
    entry_id: str,
) -> Entry | ToolExecutionResult:
    matches = find_entries_by_id(context.db, entry_id)
    if not matches:
        return error_result("no entry matched entry_id", details={"entry_id": entry_id})
    if len(matches) > 1:
        return error_result(
            "ambiguous entry_id matched multiple entries; retry with one of the candidate ids",
            details=entry_id_ambiguity_details(matches, entry_id=entry_id),
        )
    return matches[0]


def _resolve_group_proposal_reference_or_error(
    context: ToolContext,
    *,
    proposal_id: str,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> AgentChangeItem | ToolExecutionResult:
    try:
        item = resolve_proposal_by_id(context, proposal_id, detail_label="thread proposals")
    except ValueError as exc:
        return error_result("invalid proposal id", details=str(exc))
    if item is None:
        return error_result("proposal not found", details={"proposal_id": proposal_id})
    if item.change_type != AgentChangeType.CREATE_GROUP:
        return error_result(
            "proposal_id does not reference a create_group proposal",
            details={"proposal_id": proposal_id, "change_type": item.change_type.value},
        )
    if expected_statuses is not None and item.status not in expected_statuses:
        return error_result(
            "group proposal is not in a usable status",
            details={"proposal_id": item.id, "status": item.status.value},
        )
    return item


def _resolve_entry_proposal_reference_or_error(
    context: ToolContext,
    *,
    proposal_id: str,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> AgentChangeItem | ToolExecutionResult:
    try:
        item = resolve_proposal_by_id(context, proposal_id, detail_label="thread proposals")
    except ValueError as exc:
        return error_result("invalid proposal id", details=str(exc))
    if item is None:
        return error_result("proposal not found", details={"proposal_id": proposal_id})
    if item.change_type != AgentChangeType.CREATE_ENTRY:
        return error_result(
            "proposal_id does not reference a create_entry proposal",
            details={"proposal_id": proposal_id, "change_type": item.change_type.value},
        )
    if expected_statuses is not None and item.status not in expected_statuses:
        return error_result(
            "entry proposal is not in a usable status",
            details={"proposal_id": item.id, "status": item.status.value},
        )
    return item


def _canonical_group_ref_payload(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> tuple[dict[str, Any], EntryGroup | None, AgentChangeItem | None] | ToolExecutionResult:
    if group_ref.group_id is not None:
        group = _match_existing_group_or_error(context, group_id=group_ref.group_id)
        if isinstance(group, ToolExecutionResult):
            return group
        return {"group_id": group.id}, group, None

    assert group_ref.create_group_proposal_id is not None
    proposal = _resolve_group_proposal_reference_or_error(
        context,
        proposal_id=group_ref.create_group_proposal_id,
        expected_statuses=expected_statuses,
    )
    if isinstance(proposal, ToolExecutionResult):
        return proposal
    return {"create_group_proposal_id": proposal.id}, None, proposal


def _canonical_entry_ref_payload(
    context: ToolContext,
    *,
    entry_ref: EntryReferencePayload,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> tuple[dict[str, Any], Entry | None, AgentChangeItem | None] | ToolExecutionResult:
    if entry_ref.entry_id is not None:
        entry = _match_existing_entry_or_error(context, entry_id=entry_ref.entry_id)
        if isinstance(entry, ToolExecutionResult):
            return entry
        return {"entry_id": entry.id}, entry, None

    assert entry_ref.create_entry_proposal_id is not None
    proposal = _resolve_entry_proposal_reference_or_error(
        context,
        proposal_id=entry_ref.create_entry_proposal_id,
        expected_statuses=expected_statuses,
    )
    if isinstance(proposal, ToolExecutionResult):
        return proposal
    return {"create_entry_proposal_id": proposal.id}, None, proposal


def _resolved_group_type_from_ref(
    context: ToolContext,
    group_ref: GroupReferencePayload,
) -> tuple[GroupType | None, dict[str, Any], EntryGroup | None, AgentChangeItem | None] | ToolExecutionResult:
    if group_ref.group_id is not None:
        group = _match_existing_group_or_error(context, group_id=group_ref.group_id)
        if isinstance(group, ToolExecutionResult):
            return group
        return group.group_type, _group_preview_from_existing(group), group, None

    assert group_ref.create_group_proposal_id is not None
    proposal = _resolve_group_proposal_reference_or_error(
        context,
        proposal_id=group_ref.create_group_proposal_id,
        expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
    )
    if isinstance(proposal, ToolExecutionResult):
        return proposal
    payload = proposal.payload_json
    raw_type = payload.get("group_type")
    group_type = GroupType(str(raw_type)) if isinstance(raw_type, str) else None
    return group_type, _group_preview_from_proposal(proposal), None, proposal


def _resolved_member_ref_preview(
    context: ToolContext,
    *,
    entry_ref: EntryReferencePayload | None,
    child_group_ref: GroupReferencePayload | None,
    enforce_add_membership_rules: bool = True,
) -> tuple[dict[str, Any], EntryKind | None] | ToolExecutionResult:
    if entry_ref is not None:
        if entry_ref.entry_id is not None:
            matches = find_entries_by_id(context.db, entry_ref.entry_id)
            if not matches:
                return error_result("no entry matched entry_id", details={"entry_id": entry_ref.entry_id})
            if len(matches) > 1:
                return error_result(
                    "ambiguous entry_id matched multiple entries; retry with one of the candidate ids",
                    details=entry_id_ambiguity_details(matches, entry_id=entry_ref.entry_id),
                )
            entry = matches[0]
            if enforce_add_membership_rules and entry.group_membership is not None:
                return error_result("this entry already belongs to a group")
            preview = entry_to_public_record(entry)
            preview["source"] = "entry"
            return preview, entry.kind

        assert entry_ref.create_entry_proposal_id is not None
        proposal = _resolve_entry_proposal_reference_or_error(
            context,
            proposal_id=entry_ref.create_entry_proposal_id,
            expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
        )
        if isinstance(proposal, ToolExecutionResult):
            return proposal
        preview = _entry_preview_from_proposal(proposal)
        raw_kind = proposal.payload_json.get("kind")
        entry_kind = EntryKind(str(raw_kind)) if isinstance(raw_kind, str) else None
        return preview, entry_kind

    assert child_group_ref is not None
    if child_group_ref.group_id is not None:
        group = _match_existing_group_or_error(context, group_id=child_group_ref.group_id)
        if isinstance(group, ToolExecutionResult):
            return group
        if enforce_add_membership_rules and group.parent_membership is not None:
            return error_result("this child group already belongs to a parent group")
        if enforce_add_membership_rules and any(
            membership.child_group_id is not None for membership in _sorted_group_memberships(group)
        ):
            return error_result("child groups cannot themselves contain child groups")
        descendant_entries = _descendant_entries_for_group(group)
        preview = _group_preview_from_existing(group)
        preview["descendant_kinds"] = sorted({entry.kind.value for entry in descendant_entries})
        return preview, descendant_entries[0].kind if len({entry.kind for entry in descendant_entries}) == 1 and descendant_entries else None

    assert child_group_ref.create_group_proposal_id is not None
    proposal = _resolve_group_proposal_reference_or_error(
        context,
        proposal_id=child_group_ref.create_group_proposal_id,
        expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
    )
    if isinstance(proposal, ToolExecutionResult):
        return proposal
    return _group_preview_from_proposal(proposal), None


def _group_ref_signature(group_ref: GroupReferencePayload) -> tuple[str, str]:
    if group_ref.group_id is not None:
        return ("group", group_ref.group_id)
    assert group_ref.create_group_proposal_id is not None
    return ("proposal", group_ref.create_group_proposal_id)


def _entry_ref_signature(entry_ref: EntryReferencePayload) -> tuple[str, str]:
    if entry_ref.entry_id is not None:
        return ("entry", entry_ref.entry_id)
    assert entry_ref.create_entry_proposal_id is not None
    return ("proposal", entry_ref.create_entry_proposal_id)


def _group_member_signature(payload: dict[str, Any]) -> tuple[tuple[str, str], str, tuple[str, str]]:
    group_ref = GroupReferencePayload.model_validate(payload.get("group_ref"))
    if isinstance(payload.get("entry_ref"), dict):
        entry_ref = EntryReferencePayload.model_validate(payload["entry_ref"])
        return (_group_ref_signature(group_ref), "entry", _entry_ref_signature(entry_ref))
    child_group_ref = GroupReferencePayload.model_validate(payload.get("child_group_ref"))
    return (_group_ref_signature(group_ref), "group", _group_ref_signature(child_group_ref))


def _pending_group_membership_conflict(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    exclude_item_id: str | None = None,
) -> ToolExecutionResult | None:
    target_signature = _group_member_signature(payload)
    for item in pending_proposals_for_thread(context):
        if exclude_item_id is not None and item.id == exclude_item_id:
            continue
        if item.change_type not in {AgentChangeType.CREATE_GROUP_MEMBER, AgentChangeType.DELETE_GROUP_MEMBER}:
            continue
        if _group_member_signature(item.payload_json) != target_signature:
            continue
        if item.change_type == change_type:
            return error_result(
                "a matching pending group membership proposal already exists in this thread",
                details={
                    "proposal_id": item.id,
                    "proposal_short_id": proposal_short_id(item.id),
                    "change_type": item.change_type.value,
                },
            )
        return error_result(
            "a conflicting pending group membership proposal already exists; update or remove it first",
            details={
                "proposal_id": item.id,
                "proposal_short_id": proposal_short_id(item.id),
                "change_type": item.change_type.value,
            },
        )
    return None


def _pending_group_change_conflict(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    group_id: str,
    exclude_item_id: str | None = None,
) -> ToolExecutionResult | None:
    for item in pending_proposals_for_thread(context):
        if exclude_item_id is not None and item.id == exclude_item_id:
            continue
        if item.change_type not in {AgentChangeType.UPDATE_GROUP, AgentChangeType.DELETE_GROUP}:
            continue
        item_group_ref = item.payload_json.get("group_ref")
        item_group_id = None
        if isinstance(item_group_ref, dict):
            item_group_id = item_group_ref.get("group_id")
        elif isinstance(item.payload_json.get("group_id"), str):
            item_group_id = item.payload_json.get("group_id")
        if item_group_id != group_id:
            continue
        if item.change_type == change_type:
            return error_result(
                "a matching pending group proposal already exists in this thread",
                details={"proposal_id": item.id, "proposal_short_id": proposal_short_id(item.id)},
            )
        return error_result(
            "a conflicting pending group proposal already exists; update or remove it first",
            details={
                "proposal_id": item.id,
                "proposal_short_id": proposal_short_id(item.id),
                "change_type": item.change_type.value,
            },
        )
    return None


def _pending_create_group_conflict(
    context: ToolContext,
    *,
    name: str,
    group_type: str,
    exclude_item_id: str | None = None,
) -> ToolExecutionResult | None:
    for item in pending_proposals_for_thread(context):
        if exclude_item_id is not None and item.id == exclude_item_id:
            continue
        if item.change_type != AgentChangeType.CREATE_GROUP:
            continue
        if item.payload_json.get("name") != name or item.payload_json.get("group_type") != group_type:
            continue
        return error_result(
            "a matching pending group creation proposal already exists in this thread",
            details={"proposal_id": item.id, "proposal_short_id": proposal_short_id(item.id)},
        )
    return None


def _pending_group_proposal_conflict(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    exclude_item_id: str | None = None,
) -> ToolExecutionResult | None:
    if change_type == AgentChangeType.CREATE_GROUP:
        return _pending_create_group_conflict(
            context,
            name=str(payload.get("name") or ""),
            group_type=str(payload.get("group_type") or ""),
            exclude_item_id=exclude_item_id,
        )
    if change_type in {AgentChangeType.UPDATE_GROUP, AgentChangeType.DELETE_GROUP}:
        return _pending_group_change_conflict(
            context,
            change_type=change_type,
            group_id=str(payload.get("group_id") or ""),
            exclude_item_id=exclude_item_id,
        )
    if change_type in {AgentChangeType.CREATE_GROUP_MEMBER, AgentChangeType.DELETE_GROUP_MEMBER}:
        return _pending_group_membership_conflict(
            context,
            change_type=change_type,
            payload=payload,
            exclude_item_id=exclude_item_id,
        )
    return None


def _pending_parent_roles_for_group(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
) -> list[GroupMemberRole]:
    roles: list[GroupMemberRole] = []
    signature = _group_ref_signature(group_ref)
    for item in pending_proposals_for_thread(context):
        if item.change_type != AgentChangeType.CREATE_GROUP_MEMBER:
            continue
        payload = item.payload_json
        item_group_ref = payload.get("group_ref")
        if not isinstance(item_group_ref, dict):
            continue
        if _group_ref_signature(GroupReferencePayload.model_validate(item_group_ref)) != signature:
            continue
        raw_role = payload.get("member_role")
        if isinstance(raw_role, str):
            roles.append(GroupMemberRole(raw_role))
    return roles


def _existing_descendant_kinds(group: EntryGroup | None) -> set[EntryKind]:
    if group is None:
        return set()
    return {entry.kind for entry in _descendant_entries_for_group(group)}


def _validate_group_member_add_rules(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
    entry_ref: EntryReferencePayload | None,
    child_group_ref: GroupReferencePayload | None,
    member_role: GroupMemberRole | None,
) -> tuple[dict[str, Any], dict[str, Any]] | ToolExecutionResult:
    group_resolution = _resolved_group_type_from_ref(context, group_ref)
    if isinstance(group_resolution, ToolExecutionResult):
        return group_resolution
    parent_group_type, group_preview, existing_group, _group_proposal = group_resolution
    canonical_parent_ref = GroupReferencePayload.model_validate(
        {"group_id": existing_group.id} if existing_group is not None else {"create_group_proposal_id": _group_proposal.id}
    )
    member_resolution = _resolved_member_ref_preview(
        context,
        entry_ref=entry_ref,
        child_group_ref=child_group_ref,
    )
    if isinstance(member_resolution, ToolExecutionResult):
        return member_resolution
    member_preview, target_kind = member_resolution

    if child_group_ref is not None:
        canonical_child_ref_resolution = _canonical_group_ref_payload(
            context,
            group_ref=child_group_ref,
            expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
        )
        if isinstance(canonical_child_ref_resolution, ToolExecutionResult):
            return canonical_child_ref_resolution
        canonical_child_ref = GroupReferencePayload.model_validate(canonical_child_ref_resolution[0])
        if _group_ref_signature(canonical_parent_ref) == _group_ref_signature(canonical_child_ref):
            return error_result("a group cannot contain itself")

    if parent_group_type == GroupType.SPLIT:
        if member_role is None:
            return error_result("split-group adds require member_role")
        existing_parent_count = sum(
            1 for membership in _sorted_group_memberships(existing_group) if membership.member_role == GroupMemberRole.PARENT
        ) if existing_group is not None else 0
        pending_parent_count = _pending_parent_roles_for_group(context, group_ref=canonical_parent_ref).count(GroupMemberRole.PARENT)
        if member_role == GroupMemberRole.PARENT and existing_parent_count + pending_parent_count > 0:
            return error_result("split groups can have at most one parent member")
        if target_kind is not None:
            expected_kind = EntryKind.EXPENSE if member_role == GroupMemberRole.PARENT else EntryKind.INCOME
            if target_kind != expected_kind:
                return error_result(
                    "split group descendants must be EXPENSE for parent members and INCOME for child members",
                    details={"expected_kind": expected_kind.value, "actual_kind": target_kind.value},
                )
    elif member_role is not None:
        return error_result("member_role is only valid when the parent group type is SPLIT")

    if existing_group is not None and child_group_ref is not None and existing_group.parent_membership is not None:
        return error_result("nested groups cannot contain child groups")

    if parent_group_type == GroupType.RECURRING and target_kind is not None:
        descendant_kinds = _existing_descendant_kinds(existing_group)
        pending_kinds = {
            EntryKind(str(item.payload_json["member_preview"]["kind"]))
            for item in pending_proposals_for_thread(context)
            if item.change_type == AgentChangeType.CREATE_GROUP_MEMBER
            and isinstance(item.payload_json.get("group_ref"), dict)
            and _group_ref_signature(GroupReferencePayload.model_validate(item.payload_json["group_ref"])) == _group_ref_signature(canonical_parent_ref)
            and isinstance(item.payload_json.get("entry_ref"), dict)
            and isinstance(item.payload_json.get("member_preview"), dict)
            and isinstance(item.payload_json["member_preview"].get("kind"), str)
        }
        all_kinds = descendant_kinds | pending_kinds | {target_kind}
        if len(all_kinds) > 1:
            return error_result("recurring groups require all descendant entries to share the same kind")

    return group_preview, member_preview


def _validate_group_member_remove_rules(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
    entry_ref: EntryReferencePayload | None,
    child_group_ref: GroupReferencePayload | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, dict[str, Any], dict[str, Any]] | ToolExecutionResult:
    group = _match_existing_group_or_error(context, group_id=group_ref.group_id or "")
    if isinstance(group, ToolExecutionResult):
        return group

    member_resolution = _resolved_member_ref_preview(
        context,
        entry_ref=entry_ref,
        child_group_ref=child_group_ref,
        enforce_add_membership_rules=False,
    )
    if isinstance(member_resolution, ToolExecutionResult):
        return member_resolution
    member_preview, _target_kind = member_resolution

    canonical_group_ref: dict[str, Any] = {"group_id": group.id}
    canonical_entry_ref: dict[str, Any] | None = None
    canonical_child_group_ref: dict[str, Any] | None = None
    target_entry_id: str | None = None
    target_child_group_id: str | None = None

    if entry_ref is not None:
        entry = _match_existing_entry_or_error(context, entry_id=entry_ref.entry_id or "")
        if isinstance(entry, ToolExecutionResult):
            return entry
        canonical_entry_ref = {"entry_id": entry.id}
        target_entry_id = entry.id
    else:
        assert child_group_ref is not None
        child_group = _match_existing_group_or_error(context, group_id=child_group_ref.group_id or "")
        if isinstance(child_group, ToolExecutionResult):
            return child_group
        canonical_child_group_ref = {"group_id": child_group.id}
        target_child_group_id = child_group.id

    membership_exists = any(
        (membership.entry_id is not None and target_entry_id is not None and membership.entry_id == target_entry_id)
        or (
            membership.child_group_id is not None
            and target_child_group_id is not None
            and membership.child_group_id == target_child_group_id
        )
        for membership in _sorted_group_memberships(group)
    )
    if not membership_exists:
        return error_result(
            "group does not currently contain that direct member",
            details={"group_id": group.id, "member": member_preview},
        )

    return canonical_group_ref, canonical_entry_ref, canonical_child_group_ref, _group_preview_from_existing(group), member_preview


def proposal_payload_from_create_entry_args(context: ToolContext, args: ProposeCreateEntryArgs) -> dict[str, Any]:
    settings = resolve_runtime_settings(context.db)
    payload = args.model_dump(mode="json")
    currency_code = str(payload.get("currency_code") or settings.default_currency_code).strip().upper()
    payload["currency_code"] = currency_code
    return payload


def normalize_update_entry_patch_for_payload(patch_model: EntryPatchArgs) -> dict[str, Any]:
    return patch_model.model_dump(mode="json", exclude_unset=True)

TChangePayload = TypeVar("TChangePayload", bound=BaseModel)


def parse_change_payload(
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    model_type: type[TChangePayload],
) -> TChangePayload:
    parsed = parse_change_payload_model(change_type, payload)
    if not isinstance(parsed, model_type):  # pragma: no cover - enum/model map guard
        raise ValueError(f"unexpected payload model for change type: {change_type.value}")
    return parsed


def normalize_payload_for_change_type(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if change_type == AgentChangeType.CREATE_TAG:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateTagArgs,
        )
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_TAG:
        parsed = parse_change_payload(
            change_type=change_type,
            payload={"name": payload.get("name"), "patch": payload.get("patch")},
            model_type=ProposeUpdateTagArgs,
        )
        normalized_payload: dict[str, Any] = {
            "name": parsed.name,
            "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
        }
        if isinstance(payload.get("current"), dict):
            normalized_payload["current"] = payload["current"]
        return normalized_payload
    if change_type == AgentChangeType.DELETE_TAG:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeDeleteTagArgs,
        )
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.CREATE_ENTITY:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateEntityArgs,
        )
        if normalize_entity_category(parsed.category) == "account":
            raise ValueError(ACCOUNT_CATEGORY_DETAIL)
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_ENTITY:
        parsed = parse_change_payload(
            change_type=change_type,
            payload={"name": payload.get("name"), "patch": payload.get("patch")},
            model_type=ProposeUpdateEntityArgs,
        )
        if normalize_entity_category(parsed.patch.category) == "account":
            raise ValueError(ACCOUNT_CATEGORY_DETAIL)
        normalized_payload = {
            "name": parsed.name,
            "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
        }
        if isinstance(payload.get("current"), dict):
            normalized_payload["current"] = payload["current"]
        return normalized_payload
    if change_type == AgentChangeType.DELETE_ENTITY:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeDeleteEntityArgs,
        )
        normalized_payload = parsed.model_dump(mode="json")
        if isinstance(payload.get("impact_preview"), dict):
            normalized_payload["impact_preview"] = payload["impact_preview"]
        return normalized_payload
    if change_type == AgentChangeType.CREATE_ACCOUNT:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateAccountArgs,
        )
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_ACCOUNT:
        parsed = parse_change_payload(
            change_type=change_type,
            payload={"name": payload.get("name"), "patch": payload.get("patch")},
            model_type=ProposeUpdateAccountArgs,
        )
        normalized_payload = {
            "name": parsed.name,
            "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
        }
        if isinstance(payload.get("current"), dict):
            normalized_payload["current"] = payload["current"]
        return normalized_payload
    if change_type == AgentChangeType.DELETE_ACCOUNT:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeDeleteAccountArgs,
        )
        normalized_payload = parsed.model_dump(mode="json")
        if isinstance(payload.get("impact_preview"), dict):
            normalized_payload["impact_preview"] = payload["impact_preview"]
        return normalized_payload
    if change_type == AgentChangeType.CREATE_ENTRY:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateEntryArgs,
        )
        validate_create_entry_entity_references(
            context,
            from_entity=parsed.from_entity,
            to_entity=parsed.to_entity,
        )
        return proposal_payload_from_create_entry_args(context, parsed)
    if change_type == AgentChangeType.UPDATE_ENTRY:
        parsed = parse_change_payload(
            change_type=change_type,
            payload={"selector": payload.get("selector"), "patch": payload.get("patch")},
            model_type=ProposeUpdateEntryArgs,
        )
        validate_update_entry_entity_patch(context, parsed.patch)
        normalized_payload = {
            "selector": entry_selector_to_json(parsed.selector),
            "patch": normalize_update_entry_patch_for_payload(parsed.patch),
        }
        if isinstance(payload.get("target"), dict):
            normalized_payload["target"] = payload["target"]
        return normalized_payload
    if change_type == AgentChangeType.DELETE_ENTRY:
        parsed = parse_change_payload(
            change_type=change_type,
            payload={"selector": payload.get("selector")},
            model_type=ProposeDeleteEntryArgs,
        )
        normalized_payload = {
            "selector": entry_selector_to_json(parsed.selector),
        }
        if isinstance(payload.get("target"), dict):
            normalized_payload["target"] = payload["target"]
        return normalized_payload
    if change_type == AgentChangeType.CREATE_GROUP:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateGroupArgs,
        )
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_GROUP:
        parsed = parse_change_payload(
            change_type=change_type,
            payload={"group_id": payload.get("group_id"), "patch": payload.get("patch")},
            model_type=ProposeUpdateGroupArgs,
        )
        group = _match_existing_group_or_error(context, group_id=parsed.group_id)
        if isinstance(group, ToolExecutionResult):
            raise ValueError(group.output_json.get("summary", "group not found"))
        normalized_payload = {
            "group_id": group.id,
            "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
            "current": _group_preview_from_existing(group),
            "target": group_detail_public_record(group),
        }
        return normalized_payload
    if change_type == AgentChangeType.DELETE_GROUP:
        parsed = parse_change_payload(
            change_type=change_type,
            payload={"group_id": payload.get("group_id")},
            model_type=ProposeDeleteGroupArgs,
        )
        group = _match_existing_group_or_error(context, group_id=parsed.group_id)
        if isinstance(group, ToolExecutionResult):
            raise ValueError(group.output_json.get("summary", "group not found"))
        return {
            "group_id": group.id,
            "target": group_detail_public_record(group),
        }
    if change_type == AgentChangeType.CREATE_GROUP_MEMBER:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=CreateGroupMemberPayload,
        )
        previews = _validate_group_member_add_rules(
            context,
            group_ref=parsed.group_ref,
            entry_ref=parsed.entry_ref,
            child_group_ref=parsed.child_group_ref,
            member_role=parsed.member_role,
        )
        if isinstance(previews, ToolExecutionResult):
            raise ValueError(previews.output_json.get("summary", "invalid group membership"))
        group_preview, member_preview = previews
        canonical_group_ref = _canonical_group_ref_payload(
            context,
            group_ref=parsed.group_ref,
            expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
        )
        if isinstance(canonical_group_ref, ToolExecutionResult):
            raise ValueError(canonical_group_ref.output_json.get("summary", "group not found"))
        canonical_entry_ref = None
        canonical_child_group_ref = None
        if parsed.entry_ref is not None:
            resolved_entry_ref = _canonical_entry_ref_payload(
                context,
                entry_ref=parsed.entry_ref,
                expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
            )
            if isinstance(resolved_entry_ref, ToolExecutionResult):
                raise ValueError(resolved_entry_ref.output_json.get("summary", "member not found"))
            canonical_entry_ref = resolved_entry_ref[0]
        if parsed.child_group_ref is not None:
            resolved_child_group_ref = _canonical_group_ref_payload(
                context,
                group_ref=parsed.child_group_ref,
                expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
            )
            if isinstance(resolved_child_group_ref, ToolExecutionResult):
                raise ValueError(resolved_child_group_ref.output_json.get("summary", "member not found"))
            canonical_child_group_ref = resolved_child_group_ref[0]
        normalized_payload = {
            "action": "add",
            "group_ref": canonical_group_ref[0],
            "entry_ref": canonical_entry_ref,
            "child_group_ref": canonical_child_group_ref,
            "member_role": parsed.member_role.value if parsed.member_role is not None else None,
        }
        normalized_payload["group_preview"] = group_preview
        normalized_payload["member_preview"] = member_preview
        return normalized_payload
    if change_type == AgentChangeType.DELETE_GROUP_MEMBER:
        parsed = parse_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=DeleteGroupMemberPayload,
        )
        removal = _validate_group_member_remove_rules(
            context,
            group_ref=parsed.group_ref,
            entry_ref=parsed.entry_ref,
            child_group_ref=parsed.child_group_ref,
        )
        if isinstance(removal, ToolExecutionResult):
            raise ValueError(removal.output_json.get("summary", "invalid group membership"))
        canonical_group_ref, canonical_entry_ref, canonical_child_group_ref, group_preview, member_preview = removal
        normalized_payload = {
            "action": "remove",
            "group_ref": canonical_group_ref,
            "entry_ref": canonical_entry_ref,
            "child_group_ref": canonical_child_group_ref,
        }
        normalized_payload["group_preview"] = group_preview
        normalized_payload["member_preview"] = member_preview
        return normalized_payload
    raise ValueError(f"unsupported proposal change type: {change_type.value}")


def propose_create_tag(context: ToolContext, args: ProposeCreateTagArgs) -> ToolExecutionResult:
    existing = context.db.scalar(select(Tag).where(Tag.name == args.name))
    if existing is not None:
        return error_result("tag already exists", details={"name": args.name})

    payload = {"name": args.name, "type": args.type}
    item = create_change_item(
        context,
        change_type=AgentChangeType.CREATE_TAG,
        payload=payload,
        rationale_text="Agent proposed creating a tag.",
    )
    return proposal_result("proposed tag creation", preview=payload, item=item)


def propose_update_tag(context: ToolContext, args: ProposeUpdateTagArgs) -> ToolExecutionResult:
    existing = context.db.scalar(select(Tag).where(Tag.name == args.name))
    if existing is None:
        return error_result("tag not found", details={"name": args.name})

    patch = args.patch.model_dump(exclude_unset=True)
    target_name = patch.get("name")
    if target_name is not None:
        duplicate = context.db.scalar(select(Tag).where(Tag.name == target_name))
        if duplicate is not None and duplicate.id != existing.id:
            return error_result("target tag name already exists", details={"name": target_name})

    type_by_tag_id = get_single_term_name_map(
        context.db,
        taxonomy_key="tag_type",
        subject_type="tag",
        subject_ids=[existing.id],
    )
    payload = {
        "name": args.name,
        "patch": patch,
        "current": {
            "name": existing.name,
            "type": type_by_tag_id.get(str(existing.id)),
        },
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.UPDATE_TAG,
        payload=payload,
        rationale_text="Agent proposed updating a tag.",
    )
    preview = {"name": args.name, "patch": patch}
    return proposal_result("proposed tag update", preview=preview, item=item)


def propose_delete_tag(context: ToolContext, args: ProposeDeleteTagArgs) -> ToolExecutionResult:
    existing = context.db.scalar(select(Tag).where(Tag.name == args.name))
    if existing is None:
        return error_result("tag not found", details={"name": args.name})

    referenced_entry_count = int(
        context.db.scalar(
            select(func.count(Entry.id))
            .join(Entry.tags)
            .where(Tag.id == existing.id, Entry.is_deleted.is_(False))
        )
        or 0
    )
    sample_entries = list(
        context.db.scalars(
            select(Entry)
            .join(Entry.tags)
            .where(Tag.id == existing.id, Entry.is_deleted.is_(False))
            .options(selectinload(Entry.tags))
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
            .limit(5)
        )
    ) if referenced_entry_count > 0 else []

    payload = {"name": args.name}
    item = create_change_item(
        context,
        change_type=AgentChangeType.DELETE_TAG,
        payload=payload,
        rationale_text="Agent proposed deleting a tag.",
    )
    preview = {
        "name": args.name,
        "referenced_entry_count": referenced_entry_count,
        "sample_entries": [entry_to_public_record(entry) for entry in sample_entries],
    }
    return proposal_result("proposed tag deletion", preview=preview, item=item)


def propose_create_entity(context: ToolContext, args: ProposeCreateEntityArgs) -> ToolExecutionResult:
    if normalize_entity_category(args.category) == "account":
        return error_result(ACCOUNT_CATEGORY_DETAIL)
    existing = find_entity_by_name(context.db, args.name)
    if existing is not None:
        return error_result("entity already exists", details={"name": args.name})
    if has_pending_create_entity_root_proposal(context, args.name):
        return error_result(
            "entity or account already has a pending creation proposal in this thread",
            details={"name": args.name},
        )

    payload = {"name": args.name, "category": args.category}
    item = create_change_item(
        context,
        change_type=AgentChangeType.CREATE_ENTITY,
        payload=payload,
        rationale_text="Agent proposed creating an entity.",
    )
    return proposal_result("proposed entity creation", preview=payload, item=item)


def propose_update_entity(context: ToolContext, args: ProposeUpdateEntityArgs) -> ToolExecutionResult:
    existing = find_entity_by_name(context.db, args.name)
    if existing is None:
        return error_result("entity not found", details={"name": args.name})
    if is_account_entity(existing):
        return error_result(
            "account-backed entities must be managed from Accounts",
            details={"name": args.name},
        )

    patch = args.patch.model_dump(exclude_unset=True)
    if normalize_entity_category(patch.get("category")) == "account":
        return error_result(ACCOUNT_CATEGORY_DETAIL)
    target_name = patch.get("name")
    if target_name is not None:
        duplicate = find_entity_by_name(context.db, target_name)
        if duplicate is not None and duplicate.id != existing.id:
            return error_result("target entity name already exists", details={"name": target_name})

    payload = {
        "name": args.name,
        "patch": patch,
        "current": {
            "name": existing.name,
            "category": existing.category,
        },
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.UPDATE_ENTITY,
        payload=payload,
        rationale_text="Agent proposed updating an entity.",
    )
    preview = {"name": args.name, "patch": patch}
    return proposal_result("proposed entity update", preview=preview, item=item)


def propose_delete_entity(context: ToolContext, args: ProposeDeleteEntityArgs) -> ToolExecutionResult:
    existing = find_entity_by_name(context.db, args.name)
    if existing is None:
        return error_result("entity not found", details={"name": args.name})
    if is_account_entity(existing):
        return error_result(
            "account-backed entities must be managed from Accounts",
            details={"name": args.name},
        )

    impacted_entries = list(
        context.db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                or_(Entry.from_entity_id == existing.id, Entry.to_entity_id == existing.id),
            )
            .options(selectinload(Entry.tags))
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
        )
    )
    impact_records = [entry_to_public_record(entry) for entry in impacted_entries]
    impacted_account_count = int(
        context.db.scalar(select(func.count(Account.id)).where(Account.id == existing.id))
        or 0
    )

    payload = {
        "name": args.name,
        "impact_preview": {
            "entry_count": len(impact_records),
            "account_count": impacted_account_count,
            "entries": impact_records,
        },
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.DELETE_ENTITY,
        payload=payload,
        rationale_text="Agent proposed deleting an entity.",
    )
    preview = {
        "name": args.name,
        "impacted_entries": len(impact_records),
        "impacted_accounts": impacted_account_count,
    }
    return proposal_result("proposed entity deletion", preview=preview, item=item)


def propose_create_account(context: ToolContext, args: ProposeCreateAccountArgs) -> ToolExecutionResult:
    if find_entity_by_name(context.db, args.name) is not None:
        return error_result("entity name already exists", details={"name": args.name})
    if has_pending_create_entity_root_proposal(context, args.name):
        return error_result(
            "entity or account already has a pending creation proposal in this thread",
            details={"name": args.name},
        )

    payload = args.model_dump(mode="json")
    item = create_change_item(
        context,
        change_type=AgentChangeType.CREATE_ACCOUNT,
        payload=payload,
        rationale_text="Agent proposed creating an account.",
    )
    return proposal_result("proposed account creation", preview=payload, item=item)


def propose_update_account(context: ToolContext, args: ProposeUpdateAccountArgs) -> ToolExecutionResult:
    existing = find_account_by_name(context.db, args.name)
    if existing is None:
        return error_result("account not found", details={"name": args.name})

    patch = args.patch.model_dump(exclude_unset=True)
    target_name = patch.get("name")
    if target_name is not None:
        duplicate = find_entity_by_name(context.db, target_name)
        if duplicate is not None and duplicate.id != existing.id:
            return error_result("target account name already exists", details={"name": target_name})

    payload = {
        "name": args.name,
        "patch": patch,
        "current": account_payload_record(existing),
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.UPDATE_ACCOUNT,
        payload=payload,
        rationale_text="Agent proposed updating an account.",
    )
    preview = {"name": args.name, "patch": patch}
    return proposal_result("proposed account update", preview=preview, item=item)


def propose_delete_account(context: ToolContext, args: ProposeDeleteAccountArgs) -> ToolExecutionResult:
    existing = find_account_by_name(context.db, args.name)
    if existing is None:
        return error_result("account not found", details={"name": args.name})

    impacted_entry_count = int(
        context.db.scalar(
            select(func.count(Entry.id)).where(
                Entry.is_deleted.is_(False),
                or_(
                    Entry.account_id == existing.id,
                    Entry.from_entity_id == existing.id,
                    Entry.to_entity_id == existing.id,
                ),
            )
        )
        or 0
    )
    snapshot_count = int(
        context.db.scalar(select(func.count(AccountSnapshot.id)).where(AccountSnapshot.account_id == existing.id))
        or 0
    )
    payload = {
        "name": args.name,
        "impact_preview": {
            "entry_count": impacted_entry_count,
            "snapshot_count": snapshot_count,
            "current": account_payload_record(existing),
        },
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.DELETE_ACCOUNT,
        payload=payload,
        rationale_text="Agent proposed deleting an account.",
    )
    preview = {
        "name": args.name,
        "impacted_entries": impacted_entry_count,
        "snapshots": snapshot_count,
    }
    return proposal_result("proposed account deletion", preview=preview, item=item)


def propose_create_entry(context: ToolContext, args: ProposeCreateEntryArgs) -> ToolExecutionResult:
    try:
        validate_create_entry_entity_references(
            context,
            from_entity=args.from_entity,
            to_entity=args.to_entity,
        )
    except ValueError as exc:
        return error_result(str(exc))

    payload = proposal_payload_from_create_entry_args(context, args)
    item = create_change_item(
        context,
        change_type=AgentChangeType.CREATE_ENTRY,
        payload=payload,
        rationale_text="Agent proposed creating an entry.",
    )
    preview = {
        "date": payload["date"],
        "kind": payload["kind"],
        "name": payload["name"],
        "amount_minor": payload["amount_minor"],
        "currency_code": payload["currency_code"],
        "from_entity": payload["from_entity"],
        "to_entity": payload["to_entity"],
        "tags": payload["tags"],
    }
    return proposal_result("proposed entry creation", preview=preview, item=item)


def propose_create_group(context: ToolContext, args: ProposeCreateGroupArgs) -> ToolExecutionResult:
    conflict = _pending_create_group_conflict(
        context,
        name=args.name,
        group_type=args.group_type.value,
    )
    if conflict is not None:
        return conflict

    payload = {"name": args.name, "group_type": args.group_type.value}
    item = create_change_item(
        context,
        change_type=AgentChangeType.CREATE_GROUP,
        payload=payload,
        rationale_text="Agent proposed creating a group.",
    )
    return proposal_result("proposed group creation", preview=payload, item=item)


def propose_update_group(context: ToolContext, args: ProposeUpdateGroupArgs) -> ToolExecutionResult:
    group = _match_existing_group_or_error(context, group_id=args.group_id)
    if isinstance(group, ToolExecutionResult):
        return group

    conflict = _pending_group_change_conflict(
        context,
        change_type=AgentChangeType.UPDATE_GROUP,
        group_id=group.id,
    )
    if conflict is not None:
        return conflict

    patch = args.patch.model_dump(exclude_unset=True, mode="json")
    payload = {
        "group_id": group.id,
        "patch": patch,
        "current": _group_preview_from_existing(group),
        "target": group_detail_public_record(group),
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.UPDATE_GROUP,
        payload=payload,
        rationale_text="Agent proposed renaming a group.",
    )
    preview = {"group_id": group_public_id(group.id), "patch": patch}
    return proposal_result("proposed group update", preview=preview, item=item)


def propose_delete_group(context: ToolContext, args: ProposeDeleteGroupArgs) -> ToolExecutionResult:
    group = _match_existing_group_or_error(context, group_id=args.group_id)
    if isinstance(group, ToolExecutionResult):
        return group

    conflict = _pending_group_change_conflict(
        context,
        change_type=AgentChangeType.DELETE_GROUP,
        group_id=group.id,
    )
    if conflict is not None:
        return conflict

    summary = build_group_summary(group)
    payload = {
        "group_id": group.id,
        "target": group_detail_public_record(group),
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.DELETE_GROUP,
        payload=payload,
        rationale_text="Agent proposed deleting a group.",
    )
    preview = {
        "group_id": group_public_id(group.id),
        "name": summary.name,
        "direct_member_count": summary.direct_member_count,
        "descendant_entry_count": summary.descendant_entry_count,
    }
    return proposal_result("proposed group deletion", preview=preview, item=item)


def propose_update_group_membership(
    context: ToolContext,
    args: ProposeUpdateGroupMembershipArgs,
) -> ToolExecutionResult:
    if args.action == "add":
        if args.child_group_ref is not None and _group_ref_signature(args.group_ref) == _group_ref_signature(args.child_group_ref):
            return error_result("a group cannot contain itself")

        canonical_group_ref = _canonical_group_ref_payload(
            context,
            group_ref=args.group_ref,
            expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
        )
        if isinstance(canonical_group_ref, ToolExecutionResult):
            return canonical_group_ref
        canonical_entry_ref = None
        canonical_child_group_ref = None
        if args.entry_ref is not None:
            resolved_entry_ref = _canonical_entry_ref_payload(
                context,
                entry_ref=args.entry_ref,
                expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
            )
            if isinstance(resolved_entry_ref, ToolExecutionResult):
                return resolved_entry_ref
            canonical_entry_ref = resolved_entry_ref[0]
        if args.child_group_ref is not None:
            resolved_child_group_ref = _canonical_group_ref_payload(
                context,
                group_ref=args.child_group_ref,
                expected_statuses={AgentChangeStatus.PENDING_REVIEW, AgentChangeStatus.APPROVED, AgentChangeStatus.APPLIED},
            )
            if isinstance(resolved_child_group_ref, ToolExecutionResult):
                return resolved_child_group_ref
            canonical_child_group_ref = resolved_child_group_ref[0]

        payload = {
            "action": "add",
            "group_ref": canonical_group_ref[0],
            "entry_ref": canonical_entry_ref,
            "child_group_ref": canonical_child_group_ref,
            "member_role": args.member_role.value if args.member_role is not None else None,
        }
        conflict = _pending_group_membership_conflict(
            context,
            change_type=AgentChangeType.CREATE_GROUP_MEMBER,
            payload=payload,
        )
        if conflict is not None:
            return conflict

        previews = _validate_group_member_add_rules(
            context,
            group_ref=args.group_ref,
            entry_ref=args.entry_ref,
            child_group_ref=args.child_group_ref,
            member_role=args.member_role,
        )
        if isinstance(previews, ToolExecutionResult):
            return previews
        group_preview, member_preview = previews
        payload["group_preview"] = group_preview
        payload["member_preview"] = member_preview
        item = create_change_item(
            context,
            change_type=AgentChangeType.CREATE_GROUP_MEMBER,
            payload=payload,
            rationale_text="Agent proposed adding a direct group member.",
        )
        preview = {
            "action": "add",
            "group": group_preview,
            "member": member_preview,
            "member_role": payload["member_role"],
        }
        return proposal_result("proposed group membership add", preview=preview, item=item)

    removal = _validate_group_member_remove_rules(
        context,
        group_ref=args.group_ref,
        entry_ref=args.entry_ref,
        child_group_ref=args.child_group_ref,
    )
    if isinstance(removal, ToolExecutionResult):
        return removal
    canonical_group_ref, canonical_entry_ref, canonical_child_group_ref, group_preview, member_preview = removal

    payload = {
        "action": "remove",
        "group_ref": canonical_group_ref,
        "entry_ref": canonical_entry_ref,
        "child_group_ref": canonical_child_group_ref,
    }
    conflict = _pending_group_membership_conflict(
        context,
        change_type=AgentChangeType.DELETE_GROUP_MEMBER,
        payload=payload,
    )
    if conflict is not None:
        return conflict

    payload["group_preview"] = group_preview
    payload["member_preview"] = member_preview
    item = create_change_item(
        context,
        change_type=AgentChangeType.DELETE_GROUP_MEMBER,
        payload=payload,
        rationale_text="Agent proposed removing a direct group member.",
    )
    preview = {
        "action": "remove",
        "group": payload["group_preview"],
        "member": member_preview,
    }
    return proposal_result("proposed group membership removal", preview=preview, item=item)


def propose_update_entry(context: ToolContext, args: ProposeUpdateEntryArgs) -> ToolExecutionResult:
    matches = _find_entries_for_reference(
        context,
        entry_id=args.entry_id,
        selector=args.selector,
    )
    if not matches:
        return error_result(
            "no entry matched reference",
            details=_reference_details(entry_id=args.entry_id, selector=args.selector),
        )
    if len(matches) > 1:
        details = _reference_details(entry_id=args.entry_id, selector=args.selector)
        if args.entry_id is not None:
            details.update(entry_id_ambiguity_details(matches, entry_id=args.entry_id))
            return error_result(
                "ambiguous entry_id matched multiple entries; retry with one of the candidate ids",
                details=details,
            )
        return error_result(
            "ambiguous selector matched multiple entries; ask the user to clarify",
            details={
                **details,
                **entry_ambiguity_details(matches),
            },
        )

    try:
        validate_update_entry_entity_patch(context, args.patch)
    except ValueError as exc:
        return error_result(str(exc))

    patch = args.patch.model_dump(exclude_unset=True)
    if "date" in patch and patch["date"] is not None:
        patch["date"] = patch["date"].isoformat()

    matched_entry = matches[0]
    payload = {
        "entry_id": matched_entry.id,
        "selector": entry_selector_from_entry(matched_entry),
        "patch": patch,
        "target": entry_to_public_record(matched_entry),
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.UPDATE_ENTRY,
        payload=payload,
        rationale_text="Agent proposed updating an entry.",
    )
    preview = {
        "entry_id": entry_public_id(matched_entry.id),
        "selector": payload["selector"],
        "patch": patch,
    }
    return proposal_result("proposed entry update", preview=preview, item=item)


def propose_delete_entry(context: ToolContext, args: ProposeDeleteEntryArgs) -> ToolExecutionResult:
    matches = _find_entries_for_reference(
        context,
        entry_id=args.entry_id,
        selector=args.selector,
    )
    if not matches:
        return error_result(
            "no entry matched reference",
            details=_reference_details(entry_id=args.entry_id, selector=args.selector),
        )
    if len(matches) > 1:
        details = _reference_details(entry_id=args.entry_id, selector=args.selector)
        if args.entry_id is not None:
            details.update(entry_id_ambiguity_details(matches, entry_id=args.entry_id))
            return error_result(
                "ambiguous entry_id matched multiple entries; retry with one of the candidate ids",
                details=details,
            )
        return error_result(
            "ambiguous selector matched multiple entries; ask the user to clarify",
            details={
                **details,
                **entry_ambiguity_details(matches),
            },
        )

    matched_entry = matches[0]
    payload = {
        "entry_id": matched_entry.id,
        "selector": entry_selector_from_entry(matched_entry),
        "target": entry_to_public_record(matched_entry),
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.DELETE_ENTRY,
        payload=payload,
        rationale_text="Agent proposed deleting an entry.",
    )
    preview = {
        "entry_id": entry_public_id(matched_entry.id),
        "selector": payload["selector"],
        "target": payload["target"],
    }
    return proposal_result("proposed entry deletion", preview=preview, item=item)


def update_pending_proposal(context: ToolContext, args: UpdatePendingProposalArgs) -> ToolExecutionResult:
    try:
        item = resolve_pending_proposal_by_id(context, args.proposal_id)
    except ValueError as exc:
        return error_result("invalid proposal id", details=str(exc))
    if item is None:
        return error_result(
            "pending proposal not found",
            details={"proposal_id": args.proposal_id},
        )

    if item.status != AgentChangeStatus.PENDING_REVIEW:
        return error_result(
            "only pending proposals can be updated",
            details={
                "proposal_id": item.id,
                "status": item.status.value,
            },
        )

    try:
        validate_patch_map_paths(item.change_type, args.patch_map)
        patched_payload = apply_patch_map_to_payload(item.payload_json, args.patch_map)
        normalized_payload = normalize_payload_for_change_type(
            context,
            change_type=item.change_type,
            payload=patched_payload,
        )
    except ValidationError as exc:
        return error_result("invalid proposal patch", details=exc.errors())
    except ValueError as exc:
        return error_result("invalid proposal patch", details=str(exc))

    conflict = _pending_group_proposal_conflict(
        context,
        change_type=item.change_type,
        payload=normalized_payload,
        exclude_item_id=item.id,
    )
    if conflict is not None:
        return conflict

    item.payload_json = normalized_payload
    context.db.add(item)
    context.db.flush()

    output_json = {
        "status": "OK",
        "summary": "updated pending proposal",
        "proposal_id": item.id,
        "proposal_short_id": proposal_short_id(item.id),
        "change_type": item.change_type.value,
        "item_status": item.status.value,
        "patch_fields": sorted(args.patch_map),
        "preview": normalized_payload,
    }
    output_lines = [
        "OK",
        "summary: updated pending proposal",
        f"proposal_id: {item.id}",
        f"proposal_short_id: {proposal_short_id(item.id)}",
        f"change_type: {item.change_type.value}",
        f"status: {item.status.value}",
        f"patch_fields: {sorted(args.patch_map)}",
        f"preview: {normalized_payload}",
    ]
    return ToolExecutionResult(
        output_text=format_lines(output_lines),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )


def remove_pending_proposal(context: ToolContext, args: RemovePendingProposalArgs) -> ToolExecutionResult:
    try:
        item = resolve_pending_proposal_by_id(context, args.proposal_id)
    except ValueError as exc:
        return error_result("invalid proposal id", details=str(exc))
    if item is None:
        return error_result(
            "pending proposal not found",
            details={"proposal_id": args.proposal_id},
        )

    if item.status != AgentChangeStatus.PENDING_REVIEW:
        return error_result(
            "only pending proposals can be removed",
            details={
                "proposal_id": item.id,
                "status": item.status.value,
            },
        )

    removed_payload = deepcopy(item.payload_json)
    removed_change_type = item.change_type.value
    removed_item_id = item.id
    removed_short_id = proposal_short_id(item.id)

    context.db.delete(item)
    context.db.flush()

    output_json = {
        "status": "OK",
        "summary": "removed pending proposal",
        "proposal_id": removed_item_id,
        "proposal_short_id": removed_short_id,
        "change_type": removed_change_type,
        "removed": True,
        "removed_preview": removed_payload,
    }
    output_lines = [
        "OK",
        "summary: removed pending proposal",
        f"proposal_id: {removed_item_id}",
        f"proposal_short_id: {removed_short_id}",
        f"change_type: {removed_change_type}",
        "removed: true",
        f"removed_preview: {removed_payload}",
    ]
    return ToolExecutionResult(
        output_text=format_lines(output_lines),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )
