# CALLING SPEC:
# - Purpose: implement focused service logic for `entries`.
# - Inputs: callers that import `backend/services/agent/proposals/entries.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `entries`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.models_agent import AgentChangeItem
from backend.models_finance import Entry
from backend.services.agent.change_contracts.entries import (
    CreateEntryPayload as ProposeCreateEntryArgs,
    DeleteEntryPayload as ProposeDeleteEntryArgs,
    EntryReferencePayload,
    UpdateEntryPatchPayload as EntryPatchArgs,
    UpdateEntryPayload as ProposeUpdateEntryArgs,
)
from backend.services.agent.entry_references import (
    entry_id_ambiguity_details,
    entry_public_id,
    entry_to_public_record,
    find_entries_by_public_id_prefix,
)
from backend.services.agent.proposals.common import (
    create_change_item,
    has_pending_create_entity_root_proposal,
    proposal_short_id,
    proposal_result,
    require_tool_principal,
    resolve_proposal_by_id,
)
from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult
from backend.services.entities import find_entity_by_name
from backend.services.runtime_settings import resolve_runtime_settings
from backend.validation.finance_names import normalize_entity_name


def match_single_entry_reference_or_error(
    context: ToolContext,
    *,
    entry_id: str,
) -> Entry | ToolExecutionResult:
    principal = require_tool_principal(context)
    matches = find_entries_by_public_id_prefix(
        context.db,
        entry_id,
        principal_user_id=principal.user_id,
        is_admin=False,
    )
    if not matches:
        return error_result(
            "no entry matched reference",
            details={"entry_id": entry_id},
        )
    if len(matches) > 1:
        return error_result(
            "ambiguous entry_id matched multiple entries; retry with one of the candidate ids",
            details=entry_id_ambiguity_details(matches, entry_id=entry_id),
        )
    return matches[0]


def _raise_if_entry_reference_error(result: Entry | ToolExecutionResult) -> Entry:
    if isinstance(result, ToolExecutionResult):
        raise ValueError(str(result.output_json.get("summary", "invalid entry reference")))
    return result


def normalized_entry_reference_payload(
    context: ToolContext,
    *,
    entry_id: str,
) -> dict[str, Any]:
    matched_entry = _raise_if_entry_reference_error(
        match_single_entry_reference_or_error(
            context,
            entry_id=entry_id,
        )
    )
    return {
        "entry_id": matched_entry.id,
        "target": entry_to_public_record(matched_entry),
    }


def match_existing_entry_or_error(
    context: ToolContext,
    *,
    entry_id: str,
) -> Entry | ToolExecutionResult:
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    matches = find_entries_by_public_id_prefix(
        context.db,
        entry_id,
        principal_user_id=principal.user_id,
        is_admin=False,
    )
    if not matches:
        return error_result("no entry matched entry_id", details={"entry_id": entry_id})
    if len(matches) > 1:
        return error_result(
            "ambiguous entry_id matched multiple entries; retry with one of the candidate ids",
            details=entry_id_ambiguity_details(matches, entry_id=entry_id),
        )
    return matches[0]


def resolve_entry_proposal_reference_or_error(
    context: ToolContext,
    *,
    proposal_id: str,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> AgentChangeItem | ToolExecutionResult:
    item = resolve_proposal_by_id(context, proposal_id)
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


def entry_preview_from_proposal(item: AgentChangeItem) -> dict[str, Any]:
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


def validate_proposed_entity_reference(context: ToolContext, entity_name: str) -> None:
    principal = require_tool_principal(context)
    if find_entity_by_name(context.db, entity_name, owner_user_id=principal.user_id) is not None:
        return
    if has_pending_create_entity_root_proposal(context, entity_name):
        return
    raise ValueError(
        f"entity not found: '{entity_name}'. Use an existing entity or create an entity/account proposal "
        "for it in the current thread first."
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


def proposal_payload_from_create_entry_args(context: ToolContext, args: ProposeCreateEntryArgs) -> dict[str, Any]:
    settings = resolve_runtime_settings(context.db)
    payload = args.model_dump(mode="json")
    currency_code = str(payload.get("currency_code") or settings.default_currency_code).strip().upper()
    payload["currency_code"] = currency_code
    return payload


def normalize_update_entry_patch_for_payload(patch_model: EntryPatchArgs) -> dict[str, Any]:
    return patch_model.model_dump(mode="json", exclude_unset=True)


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


def propose_update_entry(context: ToolContext, args: ProposeUpdateEntryArgs) -> ToolExecutionResult:
    matched_entry = match_single_entry_reference_or_error(
        context,
        entry_id=args.entry_id,
    )
    if isinstance(matched_entry, ToolExecutionResult):
        return matched_entry

    try:
        validate_update_entry_entity_patch(context, args.patch)
    except ValueError as exc:
        return error_result(str(exc))

    patch = args.patch.model_dump(exclude_unset=True)
    if "date" in patch and patch["date"] is not None:
        patch["date"] = patch["date"].isoformat()

    payload = {
        "entry_id": matched_entry.id,
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
        "patch": patch,
    }
    return proposal_result("proposed entry update", preview=preview, item=item)


def propose_delete_entry(context: ToolContext, args: ProposeDeleteEntryArgs) -> ToolExecutionResult:
    matched_entry = match_single_entry_reference_or_error(
        context,
        entry_id=args.entry_id,
    )
    if isinstance(matched_entry, ToolExecutionResult):
        return matched_entry
    payload = {
        "entry_id": matched_entry.id,
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
        "target": payload["target"],
    }
    return proposal_result("proposed entry deletion", preview=preview, item=item)
