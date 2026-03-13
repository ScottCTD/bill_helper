# CALLING SPEC:
# - Purpose: implement focused service logic for `catalog`.
# - Inputs: callers that import `backend/services/agent/proposals/catalog.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `catalog`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from backend.enums_agent import AgentChangeType
from backend.models_finance import Account, AccountSnapshot, Entry, Tag
from backend.services.accounts import find_account_by_name
from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload as ProposeCreateAccountArgs,
    CreateEntityPayload as ProposeCreateEntityArgs,
    CreateTagPayload as ProposeCreateTagArgs,
    DeleteAccountPayload as ProposeDeleteAccountArgs,
    DeleteEntityPayload as ProposeDeleteEntityArgs,
    DeleteTagPayload as ProposeDeleteTagArgs,
    UpdateAccountPayload as ProposeUpdateAccountArgs,
    UpdateEntityPayload as ProposeUpdateEntityArgs,
    UpdateTagPayload as ProposeUpdateTagArgs,
)
from backend.services.agent.entry_references import entry_to_public_record
from backend.services.agent.proposals.common import (
    create_change_item,
    has_pending_create_entity_root_proposal,
    proposal_result,
    require_tool_principal,
)
from backend.services.agent.proposals.snapshots import (
    propose_create_snapshot,
    propose_delete_snapshot,
)
from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult
from backend.services.entities import ACCOUNT_CATEGORY_DETAIL, find_entity_by_name, is_account_entity
from backend.services.taxonomy import get_single_term_name_map
from backend.validation.finance_names import normalize_entity_category


def account_payload_record(account: Account) -> dict[str, object]:
    return {
        "name": account.name,
        "currency_code": account.currency_code,
        "is_active": account.is_active,
        "markdown_body": account.markdown_body,
    }


def propose_create_tag(context: ToolContext, args: ProposeCreateTagArgs) -> ToolExecutionResult:
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    existing = context.db.scalar(
        select(Tag).where(
            Tag.owner_user_id == principal.user_id,
            Tag.name == args.name,
        )
    )
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
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    existing = context.db.scalar(
        select(Tag).where(
            Tag.owner_user_id == principal.user_id,
            Tag.name == args.name,
        )
    )
    if existing is None:
        return error_result("tag not found", details={"name": args.name})

    patch = args.patch.model_dump(exclude_unset=True)
    target_name = patch.get("name")
    if target_name is not None:
        duplicate = context.db.scalar(
            select(Tag).where(
                Tag.owner_user_id == principal.user_id,
                Tag.name == target_name,
            )
        )
        if duplicate is not None and duplicate.id != existing.id:
            return error_result("target tag name already exists", details={"name": target_name})

    type_by_tag_id = get_single_term_name_map(
        context.db,
        taxonomy_key="tag_type",
        subject_type="tag",
        subject_ids=[existing.id],
        owner_user_id=principal.user_id,
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
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    existing = context.db.scalar(
        select(Tag).where(
            Tag.owner_user_id == principal.user_id,
            Tag.name == args.name,
        )
    )
    if existing is None:
        return error_result("tag not found", details={"name": args.name})

    referenced_entry_count = int(
        context.db.scalar(
            select(func.count(Entry.id))
            .join(Entry.tags)
            .where(
                Tag.id == existing.id,
                Entry.is_deleted.is_(False),
                Entry.owner_user_id == principal.user_id,
            )
        )
        or 0
    )
    sample_entries = (
        list(
            context.db.scalars(
                select(Entry)
                .join(Entry.tags)
                .where(
                    Tag.id == existing.id,
                    Entry.is_deleted.is_(False),
                    Entry.owner_user_id == principal.user_id,
                )
                .options(selectinload(Entry.tags))
                .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
                .limit(5)
            )
        )
        if referenced_entry_count > 0
        else []
    )

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
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    if normalize_entity_category(args.category) == "account":
        return error_result(ACCOUNT_CATEGORY_DETAIL)
    existing = find_entity_by_name(context.db, args.name, owner_user_id=principal.user_id)
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
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    existing = find_entity_by_name(context.db, args.name, owner_user_id=principal.user_id)
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
        duplicate = find_entity_by_name(context.db, target_name, owner_user_id=principal.user_id)
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
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    existing = find_entity_by_name(context.db, args.name, owner_user_id=principal.user_id)
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
                Entry.owner_user_id == principal.user_id,
                or_(Entry.from_entity_id == existing.id, Entry.to_entity_id == existing.id),
            )
            .options(selectinload(Entry.tags))
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
        )
    )
    impact_records = [entry_to_public_record(entry) for entry in impacted_entries]
    impacted_account_count = int(
        context.db.scalar(
            select(func.count(Account.id)).where(
                Account.id == existing.id,
                Account.owner_user_id == principal.user_id,
            )
        )
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
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    if find_entity_by_name(context.db, args.name, owner_user_id=principal.user_id) is not None:
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
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    existing = find_account_by_name(context.db, args.name, owner_user_id=principal.user_id)
    if existing is None:
        return error_result("account not found", details={"name": args.name})

    patch = args.patch.model_dump(exclude_unset=True)
    target_name = patch.get("name")
    if target_name is not None:
        duplicate = find_entity_by_name(context.db, target_name, owner_user_id=principal.user_id)
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
    try:
        principal = require_tool_principal(context)
    except ValueError as exc:
        return error_result(str(exc))
    existing = find_account_by_name(context.db, args.name, owner_user_id=principal.user_id)
    if existing is None:
        return error_result("account not found", details={"name": args.name})

    impacted_entry_count = int(
        context.db.scalar(
            select(func.count(Entry.id)).where(
                Entry.is_deleted.is_(False),
                Entry.owner_user_id == principal.user_id,
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
        context.db.scalar(
            select(func.count(AccountSnapshot.id)).where(AccountSnapshot.account_id == existing.id)
        )
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
