"""Proposal HTTP helpers.

CALLING SPEC:
    build_thread_tool_context(db, principal=principal, thread_id=thread_id, run_id=run_id) -> ToolContext
    list_thread_proposals(context, query=query) -> dict
    get_thread_proposal(context, proposal_id=proposal_id) -> dict
    create_thread_proposal(context, change_type=change_type, payload_json=payload_json) -> dict
    update_thread_proposal(context, proposal_id=proposal_id, patch_map=patch_map) -> dict
    remove_thread_proposal(context, proposal_id=proposal_id) -> dict

Inputs:
    - principal-scoped SQLAlchemy session, thread id, run id, and validated request data
Outputs:
    - JSON-serializable proposal record/list/delete payloads for HTTP routes
Side effects:
    - validates run/thread ownership, creates or mutates pending proposal rows, and flushes DB state
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.auth.contracts import RequestPrincipal
from backend.enums_agent import AgentChangeType
from backend.models_agent import AgentChangeItem
from backend.services.access_scope import load_agent_run_for_principal
from backend.services.agent.proposals.common import (
    proposal_short_id,
    resolve_proposal_by_id,
)
from backend.services.agent.proposals.pending import (
    remove_pending_proposal,
    update_pending_proposal,
)
from backend.services.agent.read_tools.proposals import list_proposals, proposal_to_public_record
from backend.services.agent.tool_args.proposal_admin import (
    RemovePendingProposalArgs,
    UpdatePendingProposalArgs,
)
from backend.services.agent.tool_args.read import ListProposalsArgs
from backend.services.agent.tool_runtime_support.catalog_proposals import PROPOSAL_TOOLS
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
    query: ListProposalsArgs,
) -> dict[str, Any]:
    result = list_proposals(context, query)
    return {
        "returned_count": int(result.output_json["returned_count"]),
        "total_available": int(result.output_json["total_available"]),
        "proposals": result.output_json["proposals"],
    }


def get_thread_proposal(context: ToolContext, *, proposal_id: str) -> dict[str, Any]:
    item = _load_proposal_item(context, proposal_id=proposal_id)
    return proposal_to_public_record(item)


def create_thread_proposal(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload_json: dict[str, Any],
) -> dict[str, Any]:
    definition = _proposal_definition_for_change_type(change_type)
    parsed = _validate_arguments(definition.args_model, payload_json)
    result = definition.handler(context, parsed)
    if result.status != ToolExecutionStatus.OK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.output_json.get("summary", "Proposal creation failed."),
        )
    proposal_id = str(result.output_json["proposal_id"])
    return get_thread_proposal(context, proposal_id=proposal_id)


def update_thread_proposal(
    context: ToolContext,
    *,
    proposal_id: str,
    patch_map: dict[str, Any],
) -> dict[str, Any]:
    result = update_pending_proposal(
        context,
        UpdatePendingProposalArgs(
            proposal_id=proposal_id,
            patch_map=patch_map,
        ),
    )
    if result.status != ToolExecutionStatus.OK:
        _raise_pending_proposal_error(summary=str(result.output_json.get("summary", "")), details=result.output_json)
    resolved_id = str(result.output_json["proposal_id"])
    return get_thread_proposal(context, proposal_id=resolved_id)


def remove_thread_proposal(
    context: ToolContext,
    *,
    proposal_id: str,
) -> dict[str, Any]:
    result = remove_pending_proposal(
        context,
        RemovePendingProposalArgs(proposal_id=proposal_id),
    )
    if result.status != ToolExecutionStatus.OK:
        _raise_pending_proposal_error(summary=str(result.output_json.get("summary", "")), details=result.output_json)
    return {
        "proposal_id": str(result.output_json["proposal_id"]),
        "proposal_short_id": str(result.output_json["proposal_short_id"]),
        "change_type": str(result.output_json["change_type"]),
        "removed": bool(result.output_json["removed"]),
        "removed_payload": dict(result.output_json["removed_preview"]),
    }


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


def _proposal_definition_for_change_type(change_type: AgentChangeType):
    if change_type == AgentChangeType.CREATE_GROUP_MEMBER:
        return PROPOSAL_TOOLS["propose_update_group_membership"]
    if change_type == AgentChangeType.DELETE_GROUP_MEMBER:
        return PROPOSAL_TOOLS["propose_update_group_membership"]
    tool_name = {
        AgentChangeType.CREATE_ENTRY: "propose_create_entry",
        AgentChangeType.UPDATE_ENTRY: "propose_update_entry",
        AgentChangeType.DELETE_ENTRY: "propose_delete_entry",
        AgentChangeType.CREATE_ACCOUNT: "propose_create_account",
        AgentChangeType.UPDATE_ACCOUNT: "propose_update_account",
        AgentChangeType.DELETE_ACCOUNT: "propose_delete_account",
        AgentChangeType.CREATE_SNAPSHOT: "propose_create_snapshot",
        AgentChangeType.DELETE_SNAPSHOT: "propose_delete_snapshot",
        AgentChangeType.CREATE_GROUP: "propose_create_group",
        AgentChangeType.UPDATE_GROUP: "propose_update_group",
        AgentChangeType.DELETE_GROUP: "propose_delete_group",
        AgentChangeType.CREATE_TAG: "propose_create_tag",
        AgentChangeType.UPDATE_TAG: "propose_update_tag",
        AgentChangeType.DELETE_TAG: "propose_delete_tag",
        AgentChangeType.CREATE_ENTITY: "propose_create_entity",
        AgentChangeType.UPDATE_ENTITY: "propose_update_entity",
        AgentChangeType.DELETE_ENTITY: "propose_delete_entity",
    }.get(change_type)
    if tool_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported proposal change type: {change_type.value}.",
        )
    return PROPOSAL_TOOLS[tool_name]


def _validate_arguments(args_model, payload_json: dict[str, Any]):
    try:
        return args_model.model_validate(payload_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid proposal payload: {exc}",
        ) from exc


def _raise_pending_proposal_error(*, summary: str, details: dict[str, Any]) -> None:
    if "not found" in summary:
        status_code = status.HTTP_404_NOT_FOUND
    elif "only pending proposals can be" in summary:
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=summary or "Proposal operation failed.")
