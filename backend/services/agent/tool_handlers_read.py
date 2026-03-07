from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.enums_agent import AgentChangeType
from backend.models_agent import AgentChangeItem, AgentReviewAction, AgentRun
from backend.models_finance import Entity, Entry, Tag
from backend.services.agent.entry_references import entry_to_public_record
from backend.services.agent.tool_args import (
    ListEntitiesArgs,
    ListEntriesArgs,
    ListProposalsArgs,
    ListTagsArgs,
    SendIntermediateUpdateArgs,
    normalize_loose_text,
)
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult
from backend.services.entries import normalize_tag_name
from backend.services.taxonomy import get_single_term_name_map


def format_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def string_match_rank(value: str | None, query: str | None) -> tuple[int, bool]:
    if query is None:
        return 0, True
    value_normalized = (normalize_loose_text(value) or "").lower()
    query_normalized = query.lower()
    if value_normalized == query_normalized:
        return 0, True
    if query_normalized in value_normalized:
        return 1, True
    return 99, False


def format_entry_record(record: dict[str, Any]) -> str:
    tags = record.get("tags") or []
    return (
        f"entry_id={record.get('entry_id')} {record.get('date')} {record.get('name')} "
        f"{record.get('amount_minor')} {record.get('currency_code')} "
        f"from={record.get('from_entity') or '-'} to={record.get('to_entity') or '-'} tags={tags}"
    )


def entry_ambiguity_details(entries: list[Entry]) -> dict[str, Any]:
    return {
        "candidate_count": len(entries),
        "candidates": [entry_to_public_record(entry) for entry in entries],
    }


def error_result(summary: str, *, details: Any | None = None) -> ToolExecutionResult:
    payload: dict[str, Any] = {"status": "ERROR", "summary": summary}
    lines = ["ERROR", f"summary: {summary}"]
    if details is not None:
        payload["details"] = details
        lines.append(f"details: {details}")
    return ToolExecutionResult(
        output_text=format_lines(lines),
        output_json=payload,
        status="error",
    )


def effective_entity_category(
    entity: Entity,
    *,
    category_by_entity_id: dict[str, str],
) -> str | None:
    category = category_by_entity_id.get(str(entity.id)) or entity.category
    if category is not None:
        return category
    if entity.account is not None:
        return "account"
    return None


def proposal_short_id(item_id: str) -> str:
    return item_id[:8]


def proposal_change_parts(change_type: AgentChangeType | str) -> tuple[str, str]:
    raw_value = change_type.value if isinstance(change_type, AgentChangeType) else str(change_type)
    action, _, proposal_type = raw_value.partition("_")
    return action, proposal_type


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
    return f"{change_type} payload={payload}"


def review_action_to_public_record(action: AgentReviewAction) -> dict[str, Any]:
    return {
        "action": action.action.value,
        "actor": action.actor,
        "note": action.note,
        "created_at": action.created_at.isoformat(),
    }


def proposal_to_public_record(item: AgentChangeItem) -> dict[str, Any]:
    change_action, proposal_type = proposal_change_parts(item.change_type)
    return {
        "proposal_id": item.id,
        "proposal_short_id": proposal_short_id(item.id),
        "proposal_type": proposal_type,
        "change_action": change_action,
        "change_type": item.change_type.value,
        "proposal_tool_name": f"propose_{item.change_type.value}",
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
        line += (
            f" applied_resource={record['applied_resource_type']}:{record.get('applied_resource_id')}"
        )
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
        "; ".join(format_proposal_record(record, detailed=detailed) for record in records)
        if records
        else "(none)"
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
        status="ok",
    )


def list_entries(context: ToolContext, args: ListEntriesArgs) -> ToolExecutionResult:
    conditions = [Entry.is_deleted.is_(False)]
    if args.date is not None:
        conditions.append(Entry.occurred_at == args.date)
    if args.start_date is not None:
        conditions.append(Entry.occurred_at >= args.start_date)
    if args.end_date is not None:
        conditions.append(Entry.occurred_at <= args.end_date)
    if args.kind is not None:
        conditions.append(Entry.kind == args.kind)

    candidate_rows = list(
        context.db.scalars(
            select(Entry)
            .where(*conditions)
            .options(selectinload(Entry.tags))
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
            .limit(max(args.limit * 8, 200))
        )
    )

    ranked: list[tuple[tuple[int, int, int, int, int, int], Entry]] = []
    for entry in candidate_rows:
        name_rank, name_ok = string_match_rank(entry.name, args.name)
        from_rank, from_ok = string_match_rank(entry.from_entity, args.from_entity)
        to_rank, to_ok = string_match_rank(entry.to_entity, args.to_entity)
        if not (name_ok and from_ok and to_ok):
            continue

        entry_tags = [normalize_tag_name(tag.name) for tag in entry.tags]
        tag_rank = 0
        tag_match = True
        for requested_tag in args.tags:
            best_rank = 99
            matched = False
            for existing_tag in entry_tags:
                current_rank, current_ok = string_match_rank(existing_tag, requested_tag)
                if current_ok:
                    matched = True
                    best_rank = min(best_rank, current_rank)
            if not matched:
                tag_match = False
                break
            tag_rank += best_rank
        if not tag_match:
            continue

        ranked.append(
            (
                (
                    name_rank,
                    from_rank,
                    to_rank,
                    tag_rank,
                    -entry.occurred_at.toordinal(),
                    int(-entry.created_at.timestamp()),
                ),
                entry,
            )
        )

    ranked.sort(key=lambda pair: pair[0])
    total_available = len(ranked)
    rows = [entry for _, entry in ranked[: args.limit]]
    records = [entry_to_public_record(entry) for entry in rows]
    entries_text = "; ".join(format_entry_record(record) for record in records) if records else "(none)"

    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} matching entries",
        "returned_count": len(records),
        "total_available": total_available,
        "entries": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} matching entries",
                f"entries: {entries_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def list_tags(context: ToolContext, args: ListTagsArgs) -> ToolExecutionResult:
    tags = list(context.db.scalars(select(Tag).order_by(Tag.name.asc())))
    type_by_tag_id = get_single_term_name_map(
        context.db,
        taxonomy_key="tag_type",
        subject_type="tag",
        subject_ids=[tag.id for tag in tags],
    )

    ranked: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for tag in tags:
        tag_type = type_by_tag_id.get(str(tag.id))
        name_rank, name_ok = string_match_rank(tag.name, args.name)
        type_rank, type_ok = string_match_rank(tag_type, args.type)
        if not (name_ok and type_ok):
            continue
        record = {"name": tag.name, "type": tag_type, "description": tag.description}
        ranked.append(((name_rank, type_rank, tag.name.lower()), record))

    ranked.sort(key=lambda pair: pair[0])
    total_available = len(ranked)
    records = [record for _, record in ranked[: args.limit]]
    tags_text = ", ".join(
        f"{tag['name']} ({tag['type'] or 'untyped'}"
        f"{'; description: ' + tag['description'] if tag.get('description') else ''})"
        for tag in records
    ) if records else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} matching tags",
        "returned_count": len(records),
        "total_available": total_available,
        "tags": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} matching tags",
                f"tags: {tags_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def list_entities(context: ToolContext, args: ListEntitiesArgs) -> ToolExecutionResult:
    entities = list(
        context.db.scalars(
            select(Entity)
            .options(selectinload(Entity.account))
            .order_by(func.lower(Entity.name).asc())
        )
    )
    category_by_entity_id = get_single_term_name_map(
        context.db,
        taxonomy_key="entity_category",
        subject_type="entity",
        subject_ids=[entity.id for entity in entities],
    )

    ranked: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for entity in entities:
        category = effective_entity_category(entity, category_by_entity_id=category_by_entity_id)
        name_rank, name_ok = string_match_rank(entity.name, args.name)
        category_rank, category_ok = string_match_rank(category, args.category)
        if not (name_ok and category_ok):
            continue
        record = {"name": entity.name, "category": category, "is_account": entity.account is not None}
        ranked.append(((name_rank, category_rank, entity.name.lower()), record))

    ranked.sort(key=lambda pair: pair[0])
    total_available = len(ranked)
    records = [record for _, record in ranked[: args.limit]]
    entities_text = "; ".join(
        f"{entity['name']} ({'account; ' if entity['is_account'] else ''}{entity['category'] or 'uncategorized'})"
        for entity in records
    ) if records else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} matching entities",
        "returned_count": len(records),
        "total_available": total_available,
        "entities": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} matching entities",
                f"entities: {entities_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def send_intermediate_update(_: ToolContext, args: SendIntermediateUpdateArgs) -> ToolExecutionResult:
    payload = {
        "status": "OK",
        "summary": "intermediate update shared",
        "message": args.message,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                "summary: intermediate update shared",
                f"message: {args.message}",
            ]
        ),
        output_json=payload,
        status="ok",
    )
