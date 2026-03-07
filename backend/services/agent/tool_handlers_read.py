from __future__ import annotations

from datetime import date as DateValue
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.models_finance import Entity, Entry, Tag
from backend.services.agent.entry_references import entry_to_public_record
from backend.services.agent.tool_args import (
    EmptyArgs,
    ListEntitiesArgs,
    ListEntriesArgs,
    ListTagsArgs,
    SendIntermediateUpdateArgs,
    normalize_loose_text,
)
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult
from backend.services.entries import normalize_tag_name
from backend.services.finance import aggregate_monthly_totals, aggregate_top_tags, month_window
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


def get_dashboard_summary(context: ToolContext, _: EmptyArgs) -> ToolExecutionResult:
    month = DateValue.today().strftime("%Y-%m")
    start, end = month_window(month)
    expenses, incomes = aggregate_monthly_totals(context.db, start, end)
    top_tags = aggregate_top_tags(context.db, start, end, limit=5)
    top_tags_text = "; ".join(f"{item.tag}:{item.currency_code}:{item.total_minor}" for item in top_tags) if top_tags else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"dashboard snapshot for {month}",
        "expenses_by_currency": expenses,
        "incomes_by_currency": incomes,
        "top_tags": [
            {"tag": item.tag, "currency_code": item.currency_code, "total_minor": item.total_minor}
            for item in top_tags
        ],
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: dashboard snapshot for {month}",
                f"expenses_by_currency: {expenses}",
                f"incomes_by_currency: {incomes}",
                f"top_tags: {top_tags_text}",
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
