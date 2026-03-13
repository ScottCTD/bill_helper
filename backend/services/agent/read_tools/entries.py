# CALLING SPEC:
# - Purpose: implement focused service logic for `entries`.
# - Inputs: callers that import `backend/services/agent/read_tools/entries.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `entries`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from backend.models_finance import Entry
from backend.services.agent.entry_references import entry_ambiguity_details, entry_to_public_record
from backend.services.agent.read_tools.common import format_entry_record, string_match_rank, tool_principal_scope
from backend.services.agent.tool_args.read import ListEntriesArgs
from backend.services.agent.tool_results import format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.validation.finance_names import normalize_tag_name


def list_entries(context: ToolContext, args: ListEntriesArgs) -> ToolExecutionResult:
    _principal_name, principal_user_id, _principal_is_admin = tool_principal_scope(context)

    candidate_rows: list[Entry] = []
    if principal_user_id is not None:
        conditions = [
            Entry.is_deleted.is_(False),
            Entry.owner_user_id == principal_user_id,
        ]
        if args.date is not None:
            conditions.append(Entry.occurred_at == args.date)
        if args.start_date is not None:
            conditions.append(Entry.occurred_at >= args.start_date)
        if args.end_date is not None:
            conditions.append(Entry.occurred_at <= args.end_date)
        if args.kind is not None:
            conditions.append(Entry.kind == args.kind)
        if args.source is not None:
            source_pattern = f"%{args.source}%"
            conditions.append(
                or_(
                    Entry.name.ilike(source_pattern),
                    Entry.from_entity.ilike(source_pattern),
                    Entry.to_entity.ilike(source_pattern),
                )
            )
        if args.name is not None:
            conditions.append(Entry.name.ilike(f"%{args.name}%"))
        if args.from_entity is not None:
            conditions.append(Entry.from_entity.ilike(f"%{args.from_entity}%"))
        if args.to_entity is not None:
            conditions.append(Entry.to_entity.ilike(f"%{args.to_entity}%"))

        candidate_rows = list(
            context.db.scalars(
                select(Entry)
                .where(*conditions)
                .options(selectinload(Entry.tags))
                .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
                .limit(max(args.limit * 8, 200))
            )
        )

    ranked: list[tuple[tuple[int, int, int, int, int, int, int], Entry]] = []
    for entry in candidate_rows:
        source_ranks = [
            string_match_rank(entry.name, args.source),
            string_match_rank(entry.from_entity, args.source),
            string_match_rank(entry.to_entity, args.source),
        ]
        matching_source_ranks = [rank for rank, ok in source_ranks if ok]
        source_ok = bool(matching_source_ranks) if args.source is not None else True
        source_rank = min(matching_source_ranks) if matching_source_ranks else 0
        name_rank, name_ok = string_match_rank(entry.name, args.name)
        from_rank, from_ok = string_match_rank(entry.from_entity, args.from_entity)
        to_rank, to_ok = string_match_rank(entry.to_entity, args.to_entity)
        if not (source_ok and name_ok and from_ok and to_ok):
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
                    source_rank,
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

    output_json: dict[str, Any] = {
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
        status=ToolExecutionStatus.OK,
    )


__all__ = ["entry_ambiguity_details", "list_entries"]
