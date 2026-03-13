# CALLING SPEC:
# - Purpose: implement focused service logic for `common`.
# - Inputs: callers that import `backend/services/agent/proposals/common.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `common`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.auth.contracts import RequestPrincipal
from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.models_agent import AgentChangeItem, AgentRun
from backend.services.agent.read_tools.common import tool_principal_scope
from backend.services.agent.tool_results import format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.validation.finance_names import normalize_entity_name


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


def pending_proposals_for_thread(context: ToolContext) -> list[AgentChangeItem]:
    return proposals_for_thread(context, statuses={AgentChangeStatus.PENDING_REVIEW})


def proposals_for_thread(
    context: ToolContext,
    *,
    statuses: set[AgentChangeStatus] | None = None,
    include_review_actions: bool = False,
    newest_first: bool = False,
) -> list[AgentChangeItem]:
    thread_id = context.db.scalar(select(AgentRun.thread_id).where(AgentRun.id == context.run_id))
    if thread_id is None:
        return []
    conditions = [AgentRun.thread_id == thread_id]
    if statuses is not None:
        conditions.append(AgentChangeItem.status.in_(sorted(statuses, key=lambda value: value.value)))
    statement = (
        select(AgentChangeItem)
        .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
        .where(*conditions)
    )
    if include_review_actions:
        statement = statement.options(selectinload(AgentChangeItem.review_actions))
    if newest_first:
        statement = statement.order_by(AgentChangeItem.created_at.desc(), AgentChangeItem.updated_at.desc())
    else:
        statement = statement.order_by(AgentChangeItem.created_at.asc())
    return list(
        context.db.scalars(
            statement
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


def require_tool_principal(context: ToolContext) -> RequestPrincipal:
    principal_name, principal_user_id, principal_is_admin = tool_principal_scope(context)
    if principal_user_id is None:
        raise ValueError("Tool principal is unavailable for this run.")
    return RequestPrincipal(
        user_id=principal_user_id,
        user_name=principal_name or "(unknown)",
        is_admin=principal_is_admin,
    )
