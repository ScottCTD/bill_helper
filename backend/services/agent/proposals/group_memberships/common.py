# CALLING SPEC:
# - Purpose: implement focused service logic for `common`.
# - Inputs: callers that import `backend/services/agent/proposals/group_memberships/common.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `common`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.enums_finance import EntryKind, GroupMemberRole
from backend.models_agent import AgentChangeItem
from backend.models_finance import Entry, EntryGroup
from backend.services.agent.change_contracts.entries import EntryReferencePayload
from backend.services.agent.change_contracts.groups import (
    EntryGroupMemberTargetPayload,
    GroupMemberTargetPayload,
    GroupReferencePayload,
    normalize_group_member_payload,
    parse_group_member_target_payload,
)
from backend.services.agent.entry_references import (
    entry_id_ambiguity_details,
    entry_to_public_record,
    find_entries_by_public_id_prefix,
)
from backend.services.agent.proposals.common import pending_proposals_for_thread
from backend.services.agent.proposals.entries import (
    entry_preview_from_proposal,
    match_existing_entry_or_error,
    resolve_entry_proposal_reference_or_error,
)
from backend.services.agent.proposals.groups import (
    canonical_group_ref_payload,
    descendant_entries_for_group,
    group_preview_from_existing,
    group_preview_from_proposal,
    group_ref_signature,
    match_existing_group_or_error,
    resolve_group_proposal_reference_or_error,
    sorted_group_memberships,
)
from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult


def canonical_entry_ref_payload(
    context: ToolContext,
    *,
    entry_ref: EntryReferencePayload,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> tuple[dict[str, Any], Entry | None, AgentChangeItem | None] | ToolExecutionResult:
    if entry_ref.entry_id is not None:
        entry = match_existing_entry_or_error(context, entry_id=entry_ref.entry_id)
        if isinstance(entry, ToolExecutionResult):
            return entry
        return {"entry_id": entry.id}, entry, None

    assert entry_ref.create_entry_proposal_id is not None
    proposal = resolve_entry_proposal_reference_or_error(
        context,
        proposal_id=entry_ref.create_entry_proposal_id,
        expected_statuses=expected_statuses,
    )
    if isinstance(proposal, ToolExecutionResult):
        return proposal
    return {"create_entry_proposal_id": proposal.id}, None, proposal


def canonical_group_member_target_payload(
    context: ToolContext,
    *,
    target: GroupMemberTargetPayload,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> tuple[dict[str, Any], Entry | EntryGroup | None, AgentChangeItem | None] | ToolExecutionResult:
    if isinstance(target, EntryGroupMemberTargetPayload):
        resolved_entry_ref = canonical_entry_ref_payload(
            context,
            entry_ref=target.entry_ref,
            expected_statuses=expected_statuses,
        )
        if isinstance(resolved_entry_ref, ToolExecutionResult):
            return resolved_entry_ref
        return {"target_type": "entry", "entry_ref": resolved_entry_ref[0]}, resolved_entry_ref[1], resolved_entry_ref[2]

    resolved_group_ref = canonical_group_ref_payload(
        context,
        group_ref=target.group_ref,
        expected_statuses=expected_statuses,
    )
    if isinstance(resolved_group_ref, ToolExecutionResult):
        return resolved_group_ref
    return {"target_type": "child_group", "group_ref": resolved_group_ref[0]}, resolved_group_ref[1], resolved_group_ref[2]


def resolved_group_member_target_preview(
    context: ToolContext,
    *,
    target: GroupMemberTargetPayload,
    enforce_add_membership_rules: bool = True,
) -> tuple[dict[str, Any], EntryKind | None] | ToolExecutionResult:
    if isinstance(target, EntryGroupMemberTargetPayload):
        if target.entry_ref.entry_id is not None:
            matches = find_entries_by_public_id_prefix(context.db, target.entry_ref.entry_id)
            if not matches:
                return error_result("no entry matched entry_id", details={"entry_id": target.entry_ref.entry_id})
            if len(matches) > 1:
                return error_result(
                    "ambiguous entry_id matched multiple entries; retry with one of the candidate ids",
                    details=entry_id_ambiguity_details(matches, entry_id=target.entry_ref.entry_id),
                )
            entry = matches[0]
            if enforce_add_membership_rules and entry.group_membership is not None:
                return error_result("this entry already belongs to a group")
            preview = entry_to_public_record(entry)
            preview["source"] = "entry"
            return preview, entry.kind

        proposal = resolve_entry_proposal_reference_or_error(
            context,
            proposal_id=target.entry_ref.create_entry_proposal_id or "",
            expected_statuses={
                AgentChangeStatus.PENDING_REVIEW,
                AgentChangeStatus.APPROVED,
                AgentChangeStatus.APPLIED,
            },
        )
        if isinstance(proposal, ToolExecutionResult):
            return proposal
        preview = entry_preview_from_proposal(proposal)
        raw_kind = proposal.payload_json.get("kind")
        entry_kind = EntryKind(str(raw_kind)) if isinstance(raw_kind, str) else None
        return preview, entry_kind

    if target.group_ref.group_id is not None:
        group = match_existing_group_or_error(context, group_id=target.group_ref.group_id)
        if isinstance(group, ToolExecutionResult):
            return group
        if enforce_add_membership_rules and group.parent_membership is not None:
            return error_result("this child group already belongs to a parent group")
        if enforce_add_membership_rules and any(
            membership.child_group_id is not None for membership in sorted_group_memberships(group)
        ):
            return error_result("child groups cannot themselves contain child groups")
        descendant_entries = descendant_entries_for_group(group)
        preview = group_preview_from_existing(group)
        preview["descendant_kinds"] = sorted({entry.kind.value for entry in descendant_entries})
        if len({entry.kind for entry in descendant_entries}) == 1 and descendant_entries:
            return preview, descendant_entries[0].kind
        return preview, None

    proposal = resolve_group_proposal_reference_or_error(
        context,
        proposal_id=target.group_ref.create_group_proposal_id or "",
        expected_statuses={
            AgentChangeStatus.PENDING_REVIEW,
            AgentChangeStatus.APPROVED,
            AgentChangeStatus.APPLIED,
        },
    )
    if isinstance(proposal, ToolExecutionResult):
        return proposal
    return group_preview_from_proposal(proposal), None


def group_member_signature(payload: dict[str, Any]) -> tuple[tuple[str, str], str, tuple[str, str]]:
    normalized_payload = normalize_group_member_payload(payload)
    group_ref = GroupReferencePayload.model_validate(normalized_payload.get("group_ref"))
    target = parse_group_member_target_payload(normalized_payload.get("target"))
    target_kind, target_signature = _group_member_target_signature(target)
    return (group_ref_signature(group_ref), target_kind, target_signature)


def payload_group_member_target_type(payload: dict[str, Any]) -> str | None:
    normalized_payload = normalize_group_member_payload(payload)
    target = normalized_payload.get("target")
    if not isinstance(target, dict):
        return None
    target_type = target.get("target_type")
    return target_type if isinstance(target_type, str) else None


def pending_parent_roles_for_group(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
) -> list[GroupMemberRole]:
    roles: list[GroupMemberRole] = []
    signature = group_ref_signature(group_ref)
    for item in pending_proposals_for_thread(context):
        if item.change_type != AgentChangeType.CREATE_GROUP_MEMBER:
            continue
        payload = item.payload_json
        item_group_ref = payload.get("group_ref")
        if not isinstance(item_group_ref, dict):
            continue
        if group_ref_signature(GroupReferencePayload.model_validate(item_group_ref)) != signature:
            continue
        raw_role = payload.get("member_role")
        if isinstance(raw_role, str):
            roles.append(GroupMemberRole(raw_role))
    return roles


def existing_descendant_kinds(group: EntryGroup | None) -> set[EntryKind]:
    if group is None:
        return set()
    return {entry.kind for entry in descendant_entries_for_group(group)}


def _entry_ref_signature(entry_ref: EntryReferencePayload) -> tuple[str, str]:
    if entry_ref.entry_id is not None:
        return ("entry", entry_ref.entry_id)
    assert entry_ref.create_entry_proposal_id is not None
    return ("proposal", entry_ref.create_entry_proposal_id)


def _group_member_target_signature(target: GroupMemberTargetPayload) -> tuple[str, tuple[str, str]]:
    if isinstance(target, EntryGroupMemberTargetPayload):
        return ("entry", _entry_ref_signature(target.entry_ref))
    return ("child_group", group_ref_signature(target.group_ref))
