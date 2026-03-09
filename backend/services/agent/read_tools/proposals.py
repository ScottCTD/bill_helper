from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.enums_agent import AgentChangeType
from backend.models_agent import AgentChangeItem, AgentReviewAction, AgentRun
from backend.services.agent.proposal_metadata import proposal_metadata_for_change_type
from backend.services.agent.proposals.common import proposal_short_id
from backend.services.agent.tool_args import ListProposalsArgs
from backend.services.agent.tool_results import error_result, format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus


def proposal_change_parts(change_type: AgentChangeType | str) -> tuple[str, str]:
    metadata = proposal_metadata_for_change_type(change_type)
    return metadata.change_action, metadata.proposal_type


def proposal_summary(item: AgentChangeItem) -> str:
    payload = item.payload_json
    change_type = item.change_type.value
    if change_type == AgentChangeType.CREATE_ENTRY.value:
        return (
            f"create entry {payload.get('date')} {payload.get('name')} {payload.get('amount_minor')} "
            f"{payload.get('currency_code')} from={payload.get('from_entity')} to={payload.get('to_entity')} "
            f"tags={payload.get('tags') or []}"
        )
    if change_type == AgentChangeType.UPDATE_ENTRY.value:
        target = payload.get("entry_id") or payload.get("selector") or payload.get("target")
        return f"update entry target={target} patch={payload.get('patch') or {}}"
    if change_type == AgentChangeType.DELETE_ENTRY.value:
        target = payload.get("target") or payload.get("entry_id") or payload.get("selector")
        return f"delete entry target={target}"
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
        return (
            f"remove group member group_ref={payload.get('group_ref')} "
            f"target={payload.get('target')}"
        )
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
    return f"{change_type} payload={payload}"


def review_action_to_public_record(action: AgentReviewAction) -> dict[str, Any]:
    return {
        "action": action.action.value,
        "actor": action.actor,
        "note": action.note,
        "created_at": action.created_at.isoformat(),
    }


def proposal_to_public_record(item: AgentChangeItem) -> dict[str, Any]:
    metadata = proposal_metadata_for_change_type(item.change_type)
    return {
        "proposal_id": item.id,
        "proposal_short_id": proposal_short_id(item.id),
        "proposal_type": metadata.proposal_type,
        "change_action": metadata.change_action,
        "change_type": item.change_type.value,
        "proposal_tool_name": metadata.proposal_tool_name,
        "status": item.status.value,
        "proposal_summary": proposal_summary(item),
        "rationale_text": item.rationale_text,
        "payload": deepcopy(item.payload_json),
        "review_note": item.review_note,
        "applied_resource_type": item.applied_resource_type,
        "applied_resource_id": item.applied_resource_id,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "run_id": item.run_id,
        "review_actions": [review_action_to_public_record(action) for action in item.review_actions],
    }


def proposal_ambiguity_details(items: list[AgentChangeItem], *, proposal_id: str) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "candidate_count": len(items),
        "candidate_proposal_ids": [item.id for item in items],
        "candidates": [
            {
                "proposal_id": item.id,
                "proposal_short_id": proposal_short_id(item.id),
                "change_type": item.change_type.value,
                "status": item.status.value,
                "proposal_summary": proposal_summary(item),
            }
            for item in items
        ],
    }


def format_proposal_record(record: dict[str, Any], *, detailed: bool) -> str:
    review_actions = record.get("review_actions") or []
    review_actions_text = (
        "["
        + "; ".join(
            f"{action['action']} by {action['actor']}"
            + (f" note={action['note']}" if action.get("note") else "")
            for action in review_actions
        )
        + "]"
    ) if review_actions else "[]"
    line = (
        f"proposal_short_id={record.get('proposal_short_id')} proposal_id={record.get('proposal_id')} "
        f"status={record.get('status')} change_type={record.get('change_type')} "
        f"summary={record.get('proposal_summary')}"
    )
    if record.get("review_note"):
        line += f" review_note={record['review_note']}"
    if record.get("applied_resource_type"):
        line += f" applied_resource={record['applied_resource_type']}:{record.get('applied_resource_id')}"
    line += f" review_actions={review_actions_text}"
    if detailed:
        line += f" payload={record.get('payload')}"
    return line


def proposals_for_thread(context: ToolContext) -> list[AgentChangeItem]:
    thread_id = context.db.scalar(select(AgentRun.thread_id).where(AgentRun.id == context.run_id))
    if thread_id is None:
        return []
    return list(
        context.db.scalars(
            select(AgentChangeItem)
            .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
            .where(AgentRun.thread_id == thread_id)
            .options(selectinload(AgentChangeItem.review_actions))
            .order_by(AgentChangeItem.created_at.desc(), AgentChangeItem.updated_at.desc())
        )
    )


def list_proposals(context: ToolContext, args: ListProposalsArgs) -> ToolExecutionResult:
    filtered_items = proposals_for_thread(context)
    if args.proposal_type is not None:
        filtered_items = [
            item for item in filtered_items if proposal_change_parts(item.change_type)[1] == args.proposal_type
        ]
    if args.change_action is not None:
        filtered_items = [
            item for item in filtered_items if proposal_change_parts(item.change_type)[0] == args.change_action
        ]
    if args.proposal_status is not None:
        filtered_items = [item for item in filtered_items if item.status == args.proposal_status]

    if args.proposal_id is not None:
        exact_match = next(
            (item for item in filtered_items if item.id.lower() == args.proposal_id.lower()),
            None,
        )
        if exact_match is not None:
            filtered_items = [exact_match]
        else:
            prefix_matches = [
                item for item in filtered_items if item.id.lower().startswith(args.proposal_id.lower())
            ]
            if len(prefix_matches) > 1:
                return error_result(
                    "ambiguous proposal_id matched multiple proposals; retry with one of the candidate ids",
                    details=proposal_ambiguity_details(prefix_matches, proposal_id=args.proposal_id),
                )
            filtered_items = prefix_matches

    total_available = len(filtered_items)
    records = [proposal_to_public_record(item) for item in filtered_items[: args.limit]]
    detailed = args.proposal_id is not None or len(records) <= 5
    proposals_text = (
        "; ".join(format_proposal_record(record, detailed=detailed) for record in records) if records else "(none)"
    )
    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} matching proposals",
        "returned_count": len(records),
        "total_available": total_available,
        "proposals": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} matching proposals",
                f"proposals: {proposals_text}",
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )
