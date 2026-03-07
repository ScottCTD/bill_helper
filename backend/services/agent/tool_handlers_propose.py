from __future__ import annotations

from copy import deepcopy
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.models_finance import Account, Entry, Tag
from backend.models_agent import AgentChangeItem, AgentRun
from backend.services.agent.change_contracts import (
    EntrySelectorPayload,
    validate_change_payload,
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
from backend.services.agent.proposal_patching import apply_patch_map_to_payload
from backend.services.agent.tool_args import (
    EntryPatchArgs,
    ProposeCreateEntityArgs,
    ProposeCreateEntryArgs,
    ProposeCreateTagArgs,
    ProposeDeleteEntityArgs,
    ProposeDeleteEntryArgs,
    ProposeDeleteTagArgs,
    ProposeUpdateEntityArgs,
    ProposeUpdateEntryArgs,
    ProposeUpdateTagArgs,
    RemovePendingProposalArgs,
    UpdatePendingProposalArgs,
)
from backend.services.agent.tool_handlers_read import (
    entry_ambiguity_details,
    entry_to_public_record,
    error_result,
    format_lines,
)
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult
from backend.services.entities import (
    find_entity_by_name,
    is_account_entity,
    normalize_entity_name,
)
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.taxonomy import get_single_term_name_map


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
        status="ok",
    )


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
    thread_id = context.db.scalar(select(AgentRun.thread_id).where(AgentRun.id == context.run_id))
    if thread_id is None:
        return []
    return list(
        context.db.scalars(
            select(AgentChangeItem)
            .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
            .where(
                AgentRun.thread_id == thread_id,
                AgentChangeItem.status == AgentChangeStatus.PENDING_REVIEW,
            )
            .order_by(AgentChangeItem.created_at.asc())
        )
    )


def normalized_pending_create_entity_names(
    context: ToolContext,
    *,
    exclude_item_id: str | None = None,
) -> set[str]:
    names: set[str] = set()
    for item in pending_proposals_for_thread(context):
        if exclude_item_id is not None and item.id == exclude_item_id:
            continue
        if item.change_type != AgentChangeType.CREATE_ENTITY:
            continue
        raw_name = item.payload_json.get("name")
        if not isinstance(raw_name, str):
            continue
        normalized = normalize_entity_name(raw_name)
        if normalized:
            names.add(normalized.lower())
    return names


def has_pending_create_entity_proposal(
    context: ToolContext,
    entity_name: str,
    *,
    exclude_item_id: str | None = None,
) -> bool:
    normalized = normalize_entity_name(entity_name)
    if not normalized:
        return False
    return normalized.lower() in normalized_pending_create_entity_names(
        context,
        exclude_item_id=exclude_item_id,
    )


def validate_proposed_entity_reference(context: ToolContext, entity_name: str) -> None:
    if find_entity_by_name(context.db, entity_name) is not None:
        return
    if has_pending_create_entity_proposal(context, entity_name):
        return
    raise ValueError(
        f"entity not found: '{entity_name}'. Use an existing entity or propose_create_entity "
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


def resolve_pending_proposal_by_id(context: ToolContext, proposal_id: str) -> AgentChangeItem | None:
    pending_items = pending_proposals_for_thread(context)
    if not pending_items:
        return None

    exact = next((item for item in pending_items if item.id.lower() == proposal_id.lower()), None)
    if exact is not None:
        return exact

    matches = [item for item in pending_items if item.id.lower().startswith(proposal_id.lower())]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        example_ids = [item.id[:8] for item in matches[:5]]
        raise ValueError(
            f"proposal_id '{proposal_id}' is ambiguous across pending proposals: {example_ids}"
        )
    return None


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
    parsed = validate_change_payload(change_type, payload)
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
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_ENTITY:
        parsed = parse_change_payload(
            change_type=change_type,
            payload={"name": payload.get("name"), "patch": payload.get("patch")},
            model_type=ProposeUpdateEntityArgs,
        )
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
    existing = find_entity_by_name(context.db, args.name)
    if existing is not None:
        return error_result("entity already exists", details={"name": args.name})
    if has_pending_create_entity_proposal(context, args.name):
        return error_result(
            "entity already has a pending creation proposal in this thread",
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
        status="ok",
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
        status="ok",
    )
