from __future__ import annotations

from typing import Any

from sqlalchemy import select

from backend.models_finance import EntryGroup
from backend.services.agent.group_references import (
    find_groups_by_id,
    group_detail_public_record,
    group_id_ambiguity_details,
    group_owner_condition,
    group_summary_to_public_record,
)
from backend.services.agent.read_tools.common import (
    format_group_member_record,
    format_group_relationship_record,
    string_match_rank,
    tool_principal_scope,
)
from backend.services.agent.tool_args.read import ListGroupsArgs
from backend.services.agent.tool_results import error_result, format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.services.groups import build_group_summary, group_tree_options


def list_groups(context: ToolContext, args: ListGroupsArgs) -> ToolExecutionResult:
    _principal_name, principal_user_id, _principal_is_admin = tool_principal_scope(context)

    if args.group_id is not None:
        if principal_user_id is None:
            return error_result("no group matched group_id", details={"group_id": args.group_id})
        matches = find_groups_by_id(context.db, group_id=args.group_id, owner_user_id=principal_user_id)
        if not matches:
            return error_result("no group matched group_id", details={"group_id": args.group_id})
        if len(matches) > 1:
            return error_result(
                "ambiguous group_id matched multiple groups; retry with one of the candidate ids",
                details=group_id_ambiguity_details(matches, group_id=args.group_id),
            )

        record = group_detail_public_record(matches[0])
        output_json = {
            "status": "OK",
            "summary": f"returned details for group {record['group_id']}",
            "group": record,
        }
        direct_members_text = "; ".join(
            format_group_member_record(member) for member in record.get("direct_members", [])
        ) or "(none)"
        relationships_text = "; ".join(
            format_group_relationship_record(relationship) for relationship in record.get("derived_relationships", [])
        ) or "(none)"
        return ToolExecutionResult(
            output_text=format_lines(
                [
                    "OK",
                    f"summary: returned details for group {record['group_id']}",
                    f"group: {record['group_id']} {record['name']} ({record['group_type']})",
                    (
                        "stats: "
                        f"direct_members={record.get('direct_member_count')} "
                        f"direct_entries={record.get('direct_entry_count')} "
                        f"direct_child_groups={record.get('direct_child_group_count')} "
                        f"descendants={record.get('descendant_entry_count')} "
                        f"range={record.get('first_occurred_at') or '-'} to {record.get('last_occurred_at') or '-'}"
                    ),
                    f"direct_members: {direct_members_text}",
                    f"derived_relationships: {relationships_text}",
                ]
            ),
            output_json=output_json,
            status=ToolExecutionStatus.OK,
        )

    groups = list(
        context.db.scalars(
            select(EntryGroup)
            .where(group_owner_condition(principal_user_id))
            .options(*group_tree_options())
            .order_by(EntryGroup.created_at.desc())
        )
    )

    ranked: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for group in groups:
        summary = build_group_summary(group)
        name_rank, name_ok = string_match_rank(summary.name, args.name)
        type_rank, type_ok = string_match_rank(
            summary.group_type.value,
            args.group_type.value if args.group_type is not None else None,
        )
        if not (name_ok and type_ok):
            continue
        record = group_summary_to_public_record(summary)
        ranked.append(((name_rank, type_rank, summary.name.lower()), record))

    ranked.sort(key=lambda pair: pair[0])
    total_available = len(ranked)
    records = [record for _, record in ranked[: args.limit]]
    groups_text = "; ".join(
        f"{row['group_id']} {row['name']} ({row['group_type']}, members={row['direct_member_count']})"
        for row in records
    ) if records else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} matching groups",
        "returned_count": len(records),
        "total_available": total_available,
        "groups": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} matching groups",
                f"groups: {groups_text}",
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )
