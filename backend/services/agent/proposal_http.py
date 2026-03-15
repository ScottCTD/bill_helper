"""Thread-scoped proposal HTTP helpers.

CALLING SPEC:
    build_thread_tool_context(db, principal=principal, thread_id=thread_id, run_id=run_id) -> ToolContext
    list_thread_proposals(context, proposal_type=None, proposal_status=None, change_action=None, proposal_id=None, limit=10) -> dict
    get_thread_proposal(context, proposal_id=proposal_id) -> dict
    create_thread_proposal(context, change_type=change_type, payload_json=payload_json) -> dict

Inputs:
    - principal-scoped SQLAlchemy session, thread id, run id, and validated request data
Outputs:
    - JSON-serializable proposal record/list payloads for HTTP routes
Side effects:
    - validates run/thread ownership, creates pending proposal rows, and flushes DB state
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.auth.contracts import RequestPrincipal
from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.models_agent import AgentChangeItem
from backend.services.access_scope import load_agent_run_for_principal
from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload,
    CreateEntityPayload,
    CreateTagPayload,
    DeleteAccountPayload,
    DeleteEntityPayload,
    DeleteTagPayload,
    ProposeCreateSnapshotArgs,
    ProposeDeleteSnapshotArgs,
    UpdateAccountPayload,
    UpdateEntityPayload,
    UpdateTagPayload,
)
from backend.services.agent.change_contracts.entries import (
    CreateEntryPayload,
    DeleteEntryPayload,
    UpdateEntryPayload,
)
from backend.services.agent.change_contracts.groups import (
    CreateGroupPayload,
    DeleteGroupPayload,
    UpdateGroupPayload,
)
from backend.services.agent.proposal_metadata import proposal_metadata_for_change_type
from backend.services.agent.proposals.catalog import (
    propose_create_account,
    propose_create_entity,
    propose_create_snapshot,
    propose_create_tag,
    propose_delete_account,
    propose_delete_entity,
    propose_delete_snapshot,
    propose_delete_tag,
    propose_update_account,
    propose_update_entity,
    propose_update_tag,
)
from backend.services.agent.proposals.common import (
    proposal_short_id,
    proposals_for_thread,
    resolve_proposal_by_id,
)
from backend.services.agent.proposals.entries import (
    propose_create_entry,
    propose_delete_entry,
    propose_update_entry,
)
from backend.services.agent.proposals.group_memberships import propose_update_group_membership
from backend.services.agent.proposals.groups import (
    propose_create_group,
    propose_delete_group,
    propose_update_group,
)
from backend.services.agent.tool_args.proposal_admin import ProposeUpdateGroupMembershipArgs
from backend.services.agent.tool_types import ToolContext, ToolExecutionStatus


def build_thread_tool_context(
    db: Session,
    *,
    principal: RequestPrincipal,
    thread_id: str,
    run_id: str,
) -> ToolContext:
    run = load_agent_run_for_principal(db, run_id=run_id, principal=principal)
    if run.thread_id != thread_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run does not belong to the requested thread.",
        )
    return ToolContext(
        db=db,
        run_id=run.id,
        principal_name=principal.user_name,
        principal_user_id=principal.user_id,
        principal_is_admin=principal.is_admin,
    )


def list_thread_proposals(
    context: ToolContext,
    *,
    proposal_type: str | None = None,
    proposal_status: AgentChangeStatus | None = None,
    change_action: str | None = None,
    proposal_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    filtered_items = proposals_for_thread(
        context,
        include_review_actions=True,
        newest_first=True,
    )
    if proposal_type is not None:
        filtered_items = [
            item for item in filtered_items if proposal_metadata_for_change_type(item.change_type).proposal_type == proposal_type
        ]
    if change_action is not None:
        filtered_items = [
            item for item in filtered_items if proposal_metadata_for_change_type(item.change_type).change_action == change_action
        ]
    if proposal_status is not None:
        filtered_items = [item for item in filtered_items if item.status == proposal_status]
    if proposal_id is not None:
        try:
            resolved = resolve_proposal_by_id(context, proposal_id, items=filtered_items)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        filtered_items = [] if resolved is None else [resolved]

    records = [_public_proposal_record(item) for item in filtered_items[:limit]]
    return {
        "returned_count": len(records),
        "total_available": len(filtered_items),
        "proposals": records,
    }


def get_thread_proposal(context: ToolContext, *, proposal_id: str) -> dict[str, Any]:
    item = _load_proposal_item(context, proposal_id=proposal_id)
    return _public_proposal_record(item)


def create_thread_proposal(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload_json: dict[str, Any],
) -> dict[str, Any]:
    args_model, handler = _proposal_handler_for_change_type(change_type)
    parsed = _validate_arguments(args_model, payload_json)
    result = handler(context, parsed)
    if result.status != ToolExecutionStatus.OK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.output_json.get("summary", "Proposal creation failed."),
        )
    proposal_id = str(result.output_json["proposal_id"])
    return get_thread_proposal(context, proposal_id=proposal_id)


def _load_proposal_item(context: ToolContext, *, proposal_id: str) -> AgentChangeItem:
    try:
        item = resolve_proposal_by_id(context, proposal_id, detail_label="thread proposals")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found.",
        )
    statement = (
        select(AgentChangeItem)
        .options(selectinload(AgentChangeItem.review_actions))
        .where(AgentChangeItem.id == item.id)
    )
    loaded_item = context.db.scalar(statement)
    if loaded_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found.",
        )
    return loaded_item


def _public_proposal_record(item: AgentChangeItem) -> dict[str, Any]:
    metadata = proposal_metadata_for_change_type(item.change_type)
    return {
        "proposal_id": item.id,
        "proposal_short_id": proposal_short_id(item.id),
        "proposal_type": metadata.proposal_type,
        "change_action": metadata.change_action,
        "change_type": item.change_type.value,
        "status": item.status.value,
        "proposal_summary": _proposal_summary(item),
        "rationale_text": item.rationale_text,
        "payload": dict(item.payload_json),
        "review_note": item.review_note,
        "applied_resource_type": item.applied_resource_type,
        "applied_resource_id": item.applied_resource_id,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "run_id": item.run_id,
        "review_actions": [
            {
                "id": action.id,
                "change_item_id": action.change_item_id,
                "action": action.action.value,
                "actor": action.actor,
                "note": action.note,
                "created_at": action.created_at.isoformat(),
            }
            for action in item.review_actions
        ],
    }


def _proposal_summary(item: AgentChangeItem) -> str:
    payload = item.payload_json
    change_type = item.change_type.value
    if change_type == AgentChangeType.CREATE_ENTRY.value:
        return (
            f"create entry {payload.get('date')} {payload.get('name')} {payload.get('amount_minor')} "
            f"{payload.get('currency_code')} from={payload.get('from_entity')} to={payload.get('to_entity')} "
            f"tags={payload.get('tags') or []}"
        )
    if change_type == AgentChangeType.UPDATE_ENTRY.value:
        return f"update entry target={payload.get('entry_id') or payload.get('selector')} patch={payload.get('patch') or {}}"
    if change_type == AgentChangeType.DELETE_ENTRY.value:
        return f"delete entry target={payload.get('entry_id') or payload.get('selector')}"
    if change_type == AgentChangeType.CREATE_GROUP.value:
        return f"create group name={payload.get('name')} group_type={payload.get('group_type')}"
    if change_type == AgentChangeType.UPDATE_GROUP.value:
        return f"update group group_id={payload.get('group_id')} patch={payload.get('patch') or {}}"
    if change_type == AgentChangeType.DELETE_GROUP.value:
        return f"delete group group_id={payload.get('group_id')}"
    if change_type == AgentChangeType.CREATE_GROUP_MEMBER.value:
        return (
            f"add group member group_ref={payload.get('group_ref')} "
            f"target={payload.get('target')} "
            f"member_role={payload.get('member_role')}"
        )
    if change_type == AgentChangeType.DELETE_GROUP_MEMBER.value:
        return f"remove group member group_ref={payload.get('group_ref')} target={payload.get('target')}"
    if change_type == AgentChangeType.CREATE_TAG.value:
        return f"create tag name={payload.get('name')} type={payload.get('type')}"
    if change_type == AgentChangeType.UPDATE_TAG.value:
        return f"update tag name={payload.get('name')} patch={payload.get('patch') or {}}"
    if change_type == AgentChangeType.DELETE_TAG.value:
        return f"delete tag name={payload.get('name')}"
    if change_type == AgentChangeType.CREATE_ENTITY.value:
        return f"create entity name={payload.get('name')} category={payload.get('category')}"
    if change_type == AgentChangeType.UPDATE_ENTITY.value:
        return f"update entity name={payload.get('name')} patch={payload.get('patch') or {}}"
    if change_type == AgentChangeType.DELETE_ENTITY.value:
        return f"delete entity name={payload.get('name')}"
    if change_type == AgentChangeType.CREATE_ACCOUNT.value:
        return (
            f"create account name={payload.get('name')} currency={payload.get('currency_code')} "
            f"is_active={payload.get('is_active')}"
        )
    if change_type == AgentChangeType.UPDATE_ACCOUNT.value:
        return f"update account name={payload.get('name')} patch={payload.get('patch') or {}}"
    if change_type == AgentChangeType.DELETE_ACCOUNT.value:
        return f"delete account name={payload.get('name')}"
    if change_type == AgentChangeType.CREATE_SNAPSHOT.value:
        return (
            f"create snapshot account_id={payload.get('account_id')} date={payload.get('snapshot_at')} "
            f"balance_minor={payload.get('balance_minor')}"
        )
    if change_type == AgentChangeType.DELETE_SNAPSHOT.value:
        return f"delete snapshot account_id={payload.get('account_id')} snapshot_id={payload.get('snapshot_id')}"
    return f"{change_type} payload={payload}"


def _proposal_handler_for_change_type(change_type: AgentChangeType):
    return {
        AgentChangeType.CREATE_ENTRY: (CreateEntryPayload, propose_create_entry),
        AgentChangeType.UPDATE_ENTRY: (UpdateEntryPayload, propose_update_entry),
        AgentChangeType.DELETE_ENTRY: (DeleteEntryPayload, propose_delete_entry),
        AgentChangeType.CREATE_ACCOUNT: (CreateAccountPayload, propose_create_account),
        AgentChangeType.UPDATE_ACCOUNT: (UpdateAccountPayload, propose_update_account),
        AgentChangeType.DELETE_ACCOUNT: (DeleteAccountPayload, propose_delete_account),
        AgentChangeType.CREATE_SNAPSHOT: (ProposeCreateSnapshotArgs, propose_create_snapshot),
        AgentChangeType.DELETE_SNAPSHOT: (ProposeDeleteSnapshotArgs, propose_delete_snapshot),
        AgentChangeType.CREATE_GROUP: (CreateGroupPayload, propose_create_group),
        AgentChangeType.UPDATE_GROUP: (UpdateGroupPayload, propose_update_group),
        AgentChangeType.DELETE_GROUP: (DeleteGroupPayload, propose_delete_group),
        AgentChangeType.CREATE_GROUP_MEMBER: (ProposeUpdateGroupMembershipArgs, propose_update_group_membership),
        AgentChangeType.DELETE_GROUP_MEMBER: (ProposeUpdateGroupMembershipArgs, propose_update_group_membership),
        AgentChangeType.CREATE_TAG: (CreateTagPayload, propose_create_tag),
        AgentChangeType.UPDATE_TAG: (UpdateTagPayload, propose_update_tag),
        AgentChangeType.DELETE_TAG: (DeleteTagPayload, propose_delete_tag),
        AgentChangeType.CREATE_ENTITY: (CreateEntityPayload, propose_create_entity),
        AgentChangeType.UPDATE_ENTITY: (UpdateEntityPayload, propose_update_entity),
        AgentChangeType.DELETE_ENTITY: (DeleteEntityPayload, propose_delete_entity),
    }.get(change_type) or _raise_unsupported_change_type(change_type)


def _raise_unsupported_change_type(change_type: AgentChangeType):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported proposal change type: {change_type.value}.",
    )


def _validate_arguments(args_model, payload_json: dict[str, Any]):
    try:
        return args_model.model_validate(payload_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid proposal payload: {exc}",
        ) from exc
