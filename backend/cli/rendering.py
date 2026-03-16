"""Rendering helpers for `bh` compact/text/json output modes.

CALLING SPEC:
    render_output(payload, output_format, render_key) -> str

Inputs:
    - decoded API payloads plus the command-specific render key
Outputs:
    - compact, text, or json strings suitable for stdout
Side effects:
    - none
"""

from __future__ import annotations

import json
from typing import Any

from backend.cli.reference import compact_schema_for
from backend.cli.rendering_support import (
    bool_text,
    compact_row,
    compact_table,
    detail_block,
    escape_compact,
    render_compact_fallback,
    render_status_compact,
    render_status_text,
    render_text_fallback,
    text_table,
    unique_short_ids,
)


def render_output(payload: Any, *, output_format: str, render_key: str | None) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True)
    if output_format == "compact":
        return _render_compact(payload, render_key=render_key)
    return _render_text(payload, render_key=render_key)


def _render_compact(payload: Any, *, render_key: str | None) -> str:
    if not isinstance(payload, (dict, list)):
        return str(payload)
    renderer = _COMPACT_RENDERERS.get(render_key or "", render_compact_fallback)
    return renderer(payload)


def _render_text(payload: Any, *, render_key: str | None) -> str:
    if not isinstance(payload, (dict, list)):
        return str(payload)
    renderer = _TEXT_RENDERERS.get(render_key or "", render_text_fallback)
    return renderer(payload)


def _render_entries_list_compact(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    short_ids = unique_short_ids(item.get("id") for item in items)
    rows = [
        [
            short_ids.get(str(item.get("id")), item.get("id") or "-"),
            item.get("occurred_at") or "-",
            item.get("kind") or "-",
            item.get("amount_minor") or 0,
            item.get("currency_code") or "-",
            item.get("name") or "-",
            item.get("from_entity") or "-",
            item.get("to_entity") or "-",
            ",".join(sorted(tag.get("name") or "-" for tag in item.get("tags") or [])) or "-",
        ]
        for item in items
    ]
    return compact_table(
        summary=f"returned {len(items)} of {payload.get('total', len(items))} matching entries",
        schema_key="entries_list",
        rows=rows,
    )


def _render_entries_list_text(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    short_ids = unique_short_ids(item.get("id") for item in items)
    rows = [
        [
            short_ids.get(str(item.get("id")), item.get("id") or "-"),
            item.get("occurred_at") or "-",
            item.get("kind") or "-",
            f"{item.get('amount_minor') or 0} {item.get('currency_code') or '-'}",
            item.get("name") or "-",
            item.get("from_entity") or "-",
            item.get("to_entity") or "-",
            ",".join(sorted(tag.get("name") or "-" for tag in item.get("tags") or [])) or "-",
        ]
        for item in items
    ]
    return text_table(
        title=f"Entries ({len(items)} of {payload.get('total', len(items))})",
        headers=["ID", "Date", "Kind", "Amount", "Name", "From", "To", "Tags"],
        rows=rows,
        empty_text="(none)",
    )


def _render_entry_detail_compact(payload: dict[str, Any]) -> str:
    lines = [
        compact_table(
            summary="entry detail",
            schema_key="entries_detail",
            rows=[
                [
                    payload.get("id") or "-",
                    payload.get("occurred_at") or "-",
                    payload.get("kind") or "-",
                    payload.get("amount_minor") or 0,
                    payload.get("currency_code") or "-",
                    payload.get("name") or "-",
                    payload.get("from_entity") or "-",
                    payload.get("to_entity") or "-",
                    ",".join(sorted(tag.get("name") or "-" for tag in payload.get("tags") or [])) or "-",
                    payload.get("account_id") or "-",
                    (payload.get("direct_group") or {}).get("id") or "-",
                    payload.get("direct_group_member_role") or "-",
                ]
            ],
        )
    ]
    if payload.get("markdown_body"):
        lines.append(f"notes: {escape_compact(payload['markdown_body'])}")
    return "\n".join(lines)


def _render_entry_detail_text(payload: dict[str, Any]) -> str:
    tags = ", ".join(sorted(tag.get("name") or "-" for tag in payload.get("tags") or [])) or "-"
    lines = [
        detail_block(
            "Entry",
            [
                ("ID", payload.get("id")),
                ("Date", payload.get("occurred_at")),
                ("Kind", payload.get("kind")),
                ("Amount", f"{payload.get('amount_minor') or 0} {payload.get('currency_code') or '-'}"),
                ("Name", payload.get("name")),
                ("From", payload.get("from_entity") or "-"),
                ("To", payload.get("to_entity") or "-"),
                ("Tags", tags),
                ("Account", payload.get("account_id") or "-"),
                ("Direct Group", (payload.get("direct_group") or {}).get("id") or "-"),
                ("Group Role", payload.get("direct_group_member_role") or "-"),
            ],
        )
    ]
    if payload.get("markdown_body"):
        lines.extend(["", "Notes", payload["markdown_body"]])
    return "\n".join(lines)


def _render_accounts_list_compact(payload: list[dict[str, Any]]) -> str:
    short_ids = unique_short_ids(item.get("id") for item in payload)
    rows = [
        [
            short_ids.get(str(item.get("id")), item.get("id") or "-"),
            item.get("name") or "-",
            item.get("currency_code") or "-",
            bool_text(item.get("is_active")),
        ]
        for item in payload
    ]
    return compact_table(summary=f"returned {len(rows)} account(s)", schema_key="accounts_list", rows=rows)


def _render_accounts_list_text(payload: list[dict[str, Any]]) -> str:
    short_ids = unique_short_ids(item.get("id") for item in payload)
    rows = [
        [
            short_ids.get(str(item.get("id")), item.get("id") or "-"),
            item.get("name") or "-",
            item.get("currency_code") or "-",
            bool_text(item.get("is_active")),
        ]
        for item in payload
    ]
    return text_table(
        title="Accounts",
        headers=["ID", "Name", "Currency", "Active"],
        rows=rows,
        empty_text="(none)",
    )


def _render_accounts_snapshots_compact(payload: list[dict[str, Any]]) -> str:
    short_ids = unique_short_ids(item.get("id") for item in payload)
    rows = [
        [
            short_ids.get(str(item.get("id")), item.get("id") or "-"),
            item.get("snapshot_at") or "-",
            item.get("balance_minor") or 0,
            item.get("note") or "-",
        ]
        for item in payload
    ]
    return compact_table(summary=f"returned {len(rows)} snapshot(s)", schema_key="accounts_snapshots", rows=rows)


def _render_accounts_snapshots_text(payload: list[dict[str, Any]]) -> str:
    short_ids = unique_short_ids(item.get("id") for item in payload)
    rows = [
        [
            short_ids.get(str(item.get("id")), item.get("id") or "-"),
            item.get("snapshot_at") or "-",
            item.get("balance_minor") or 0,
            item.get("note") or "-",
        ]
        for item in payload
    ]
    return text_table(
        title="Snapshots",
        headers=["ID", "Date", "Balance Minor", "Note"],
        rows=rows,
        empty_text="(none)",
    )


def _render_accounts_reconciliation_compact(payload: dict[str, Any]) -> str:
    interval_rows = [
        [
            (interval.get("start_snapshot") or {}).get("snapshot_at") or "-",
            (interval.get("end_snapshot") or {}).get("snapshot_at") or "-",
            bool_text(interval.get("is_open")),
            interval.get("tracked_change_minor") or 0,
            interval.get("bank_change_minor") if interval.get("bank_change_minor") is not None else "-",
            interval.get("delta_minor") if interval.get("delta_minor") is not None else "-",
            interval.get("entry_count") or 0,
        ]
        for interval in payload.get("intervals") or []
    ]
    lines = [
        "OK",
        f"account: {escape_compact(payload.get('account_name') or '-')}",
        f"currency: {escape_compact(payload.get('currency_code') or '-')}",
        f"as_of: {escape_compact(payload.get('as_of') or '-')}",
        f"schema: {compact_schema_for('accounts_reconciliation')}",
    ]
    if interval_rows:
        lines.extend(compact_row(row) for row in interval_rows)
    else:
        lines.append("(none)")
    return "\n".join(lines)


def _render_accounts_reconciliation_text(payload: dict[str, Any]) -> str:
    header = detail_block(
        "Reconciliation",
        [
            ("Account", payload.get("account_name")),
            ("Currency", payload.get("currency_code")),
            ("As Of", payload.get("as_of")),
        ],
    )
    rows = [
        [
            (interval.get("start_snapshot") or {}).get("snapshot_at") or "-",
            (interval.get("end_snapshot") or {}).get("snapshot_at") or "-",
            bool_text(interval.get("is_open")),
            interval.get("tracked_change_minor") or 0,
            interval.get("bank_change_minor") if interval.get("bank_change_minor") is not None else "-",
            interval.get("delta_minor") if interval.get("delta_minor") is not None else "-",
            interval.get("entry_count") or 0,
        ]
        for interval in payload.get("intervals") or []
    ]
    return header + "\n\n" + text_table(
        title="Intervals",
        headers=["Start", "End", "Open", "Tracked", "Bank", "Delta", "Entries"],
        rows=rows,
        empty_text="(none)",
    )


def _render_groups_list_compact(payload: list[dict[str, Any]]) -> str:
    short_ids = unique_short_ids(item.get("id") for item in payload)
    rows = [
        [
            short_ids.get(str(item.get("id")), item.get("id") or "-"),
            item.get("group_type") or "-",
            item.get("name") or "-",
            item.get("descendant_entry_count") or 0,
            item.get("first_occurred_at") or "-",
            item.get("last_occurred_at") or "-",
        ]
        for item in payload
    ]
    return compact_table(summary=f"returned {len(rows)} group(s)", schema_key="groups_list", rows=rows)


def _render_groups_list_text(payload: list[dict[str, Any]]) -> str:
    short_ids = unique_short_ids(item.get("id") for item in payload)
    rows = [
        [
            short_ids.get(str(item.get("id")), item.get("id") or "-"),
            item.get("group_type") or "-",
            item.get("name") or "-",
            item.get("descendant_entry_count") or 0,
            item.get("first_occurred_at") or "-",
            item.get("last_occurred_at") or "-",
        ]
        for item in payload
    ]
    return text_table(
        title="Groups",
        headers=["ID", "Type", "Name", "Descendants", "First Date", "Last Date"],
        rows=rows,
        empty_text="(none)",
    )


def _render_group_detail_compact(payload: dict[str, Any]) -> str:
    node_rows = [
        [
            node.get("subject_id") or "-",
            node.get("node_type") or "-",
            node.get("name") or "-",
            node.get("member_role") or "-",
            node.get("occurred_at") or node.get("representative_occurred_at") or "-",
            node.get("kind") or "-",
            node.get("amount_minor") if node.get("amount_minor") is not None else "-",
            node.get("group_type") or "-",
            node.get("descendant_entry_count") if node.get("descendant_entry_count") is not None else "-",
        ]
        for node in payload.get("nodes") or []
    ]
    edge_rows = [
        [edge.get("source_graph_id") or "-", edge.get("target_graph_id") or "-", edge.get("group_type") or "-"]
        for edge in payload.get("edges") or []
    ]
    lines = [
        "OK",
        f"group_id: {escape_compact(payload.get('id') or '-')}",
        f"name: {escape_compact(payload.get('name') or '-')}",
        f"type: {escape_compact(payload.get('group_type') or '-')}",
        f"descendants: {payload.get('descendant_entry_count') or 0}",
        f"nodes_schema: {compact_schema_for('groups_nodes')}",
    ]
    lines.extend(compact_row(row) for row in node_rows) if node_rows else lines.append("(none)")
    lines.append(f"edges_schema: {compact_schema_for('groups_edges')}")
    lines.extend(compact_row(row) for row in edge_rows) if edge_rows else lines.append("(none)")
    return "\n".join(lines)


def _render_group_detail_text(payload: dict[str, Any]) -> str:
    header = detail_block(
        "Group",
        [
            ("ID", payload.get("id")),
            ("Name", payload.get("name")),
            ("Type", payload.get("group_type")),
            ("Parent", payload.get("parent_group_id") or "-"),
            ("Direct Members", payload.get("direct_member_count") or 0),
            ("Descendant Entries", payload.get("descendant_entry_count") or 0),
            ("First Date", payload.get("first_occurred_at") or "-"),
            ("Last Date", payload.get("last_occurred_at") or "-"),
        ],
    )
    node_rows = [
        [
            node.get("subject_id") or "-",
            node.get("node_type") or "-",
            node.get("name") or "-",
            node.get("member_role") or "-",
            node.get("occurred_at") or node.get("representative_occurred_at") or "-",
            node.get("kind") or "-",
            node.get("amount_minor") if node.get("amount_minor") is not None else "-",
            node.get("group_type") or "-",
        ]
        for node in payload.get("nodes") or []
    ]
    edge_rows = [
        [edge.get("source_graph_id") or "-", edge.get("target_graph_id") or "-", edge.get("group_type") or "-"]
        for edge in payload.get("edges") or []
    ]
    return (
        header
        + "\n\n"
        + text_table(
            title="Nodes",
            headers=["ID", "Type", "Name", "Role", "Date", "Kind", "Amount", "Group Type"],
            rows=node_rows,
            empty_text="(none)",
        )
        + "\n\n"
        + text_table(
            title="Edges",
            headers=["Source", "Target", "Relation"],
            rows=edge_rows,
            empty_text="(none)",
        )
    )


def _render_entities_list_compact(payload: list[dict[str, Any]]) -> str:
    rows = [[item.get("name") or "-", item.get("category") or "-"] for item in payload]
    return compact_table(summary=f"returned {len(rows)} entity record(s)", schema_key="entities_list", rows=rows)


def _render_entities_list_text(payload: list[dict[str, Any]]) -> str:
    rows = [[item.get("name") or "-", item.get("category") or "-"] for item in payload]
    return text_table(title="Entities", headers=["Name", "Category"], rows=rows, empty_text="(none)")


def _render_tags_list_compact(payload: list[dict[str, Any]]) -> str:
    rows = [[item.get("name") or "-", item.get("type") or "-", item.get("description") or "-"] for item in payload]
    return compact_table(summary=f"returned {len(rows)} tag(s)", schema_key="tags_list", rows=rows)


def _render_tags_list_text(payload: list[dict[str, Any]]) -> str:
    rows = [[item.get("name") or "-", item.get("type") or "-", item.get("description") or "-"] for item in payload]
    return text_table(title="Tags", headers=["Name", "Type", "Description"], rows=rows, empty_text="(none)")


def _render_proposals_list_compact(payload: dict[str, Any]) -> str:
    rows = [
        [item.get("proposal_short_id") or item.get("proposal_id") or "-", item.get("status") or "-", item.get("change_type") or "-", item.get("proposal_summary") or "-"]
        for item in payload.get("proposals") or []
    ]
    return compact_table(
        summary=f"returned {payload.get('returned_count', len(rows))} of {payload.get('total_available', len(rows))} matching proposals",
        schema_key="proposals_list",
        rows=rows,
    )


def _render_proposals_list_text(payload: dict[str, Any]) -> str:
    rows = [
        [item.get("proposal_short_id") or item.get("proposal_id") or "-", item.get("status") or "-", item.get("change_type") or "-", item.get("proposal_summary") or "-"]
        for item in payload.get("proposals") or []
    ]
    return text_table(
        title=f"Proposals ({payload.get('returned_count', len(rows))} of {payload.get('total_available', len(rows))})",
        headers=["ID", "Status", "Change Type", "Summary"],
        rows=rows,
        empty_text="(none)",
    )


def _render_proposal_detail_compact(payload: dict[str, Any]) -> str:
    applied_resource = "-"
    if payload.get("applied_resource_type"):
        applied_resource = f"{payload.get('applied_resource_type')}:{payload.get('applied_resource_id') or '-'}"
    lines = [
        compact_table(
            summary="proposal detail",
            schema_key="proposals_detail",
            rows=[
                [
                    payload.get("proposal_id") or "-",
                    payload.get("status") or "-",
                    payload.get("proposal_type") or "-",
                    payload.get("change_action") or "-",
                    payload.get("change_type") or "-",
                    payload.get("proposal_summary") or "-",
                    applied_resource,
                ]
            ],
        ),
        f"payload_json: {escape_compact(json.dumps(payload.get('payload') or {}, sort_keys=True, separators=(',', ':')))}",
    ]
    review_actions = payload.get("review_actions") or []
    lines.append(f"review_schema: {compact_schema_for('proposal_reviews')}")
    if review_actions:
        lines.extend(
            compact_row(
                [action.get("action") or "-", action.get("actor") or "-", action.get("note") or "-", action.get("created_at") or "-"]
            )
            for action in review_actions
        )
    else:
        lines.append("(none)")
    return "\n".join(lines)


def _render_proposal_detail_text(payload: dict[str, Any]) -> str:
    applied_resource = "-"
    if payload.get("applied_resource_type"):
        applied_resource = f"{payload.get('applied_resource_type')}:{payload.get('applied_resource_id') or '-'}"
    review_rows = [
        [action.get("action") or "-", action.get("actor") or "-", action.get("note") or "-", action.get("created_at") or "-"]
        for action in payload.get("review_actions") or []
    ]
    return (
        detail_block(
            "Proposal",
            [
                ("ID", payload.get("proposal_id")),
                ("Short ID", payload.get("proposal_short_id") or "-"),
                ("Status", payload.get("status")),
                ("Proposal Type", payload.get("proposal_type")),
                ("Change Action", payload.get("change_action")),
                ("Change Type", payload.get("change_type")),
                ("Summary", payload.get("proposal_summary")),
                ("Applied Resource", applied_resource),
            ],
        )
        + "\n\nPayload\n"
        + json.dumps(payload.get("payload") or {}, indent=2, sort_keys=True)
        + "\n\n"
        + text_table(
            title="Review Actions",
            headers=["Action", "Actor", "Note", "Created"],
            rows=review_rows,
            empty_text="(none)",
        )
    )


_COMPACT_RENDERERS = {
    "status": render_status_compact,
    "entries_list": _render_entries_list_compact,
    "entries_detail": _render_entry_detail_compact,
    "accounts_list": _render_accounts_list_compact,
    "accounts_snapshots": _render_accounts_snapshots_compact,
    "accounts_reconciliation": _render_accounts_reconciliation_compact,
    "groups_list": _render_groups_list_compact,
    "groups_detail": _render_group_detail_compact,
    "entities_list": _render_entities_list_compact,
    "tags_list": _render_tags_list_compact,
    "proposals_list": _render_proposals_list_compact,
    "proposals_detail": _render_proposal_detail_compact,
}

_TEXT_RENDERERS = {
    "status": render_status_text,
    "entries_list": _render_entries_list_text,
    "entries_detail": _render_entry_detail_text,
    "accounts_list": _render_accounts_list_text,
    "accounts_snapshots": _render_accounts_snapshots_text,
    "accounts_reconciliation": _render_accounts_reconciliation_text,
    "groups_list": _render_groups_list_text,
    "groups_detail": _render_group_detail_text,
    "entities_list": _render_entities_list_text,
    "tags_list": _render_tags_list_text,
    "proposals_list": _render_proposals_list_text,
    "proposals_detail": _render_proposal_detail_text,
}
