from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.models_finance import EntryGroup
from backend.schemas_finance import GroupGraphRead, GroupSummaryRead
from backend.services.agent.entry_references import entry_public_id
from backend.services.groups import build_group_graph, build_group_summary, group_tree_options

GROUP_PUBLIC_ID_LENGTH = 8


def group_public_id(group_id: str, *, full: bool = False) -> str:
    normalized = str(group_id)
    return normalized if full else normalized[:GROUP_PUBLIC_ID_LENGTH]


def group_owner_condition(user_id: str):
    return or_(EntryGroup.owner_user_id == user_id, EntryGroup.owner_user_id.is_(None))


def group_summary_to_public_record(summary: GroupSummaryRead, *, full_id: bool = False) -> dict[str, Any]:
    return {
        "group_id": group_public_id(summary.id, full=full_id),
        "name": summary.name,
        "group_type": summary.group_type.value if hasattr(summary.group_type, "value") else str(summary.group_type),
        "parent_group_id": group_public_id(summary.parent_group_id, full=full_id)
        if summary.parent_group_id is not None
        else None,
        "direct_member_count": summary.direct_member_count,
        "direct_entry_count": summary.direct_entry_count,
        "direct_child_group_count": summary.direct_child_group_count,
        "descendant_entry_count": summary.descendant_entry_count,
        "first_occurred_at": summary.first_occurred_at.isoformat() if summary.first_occurred_at is not None else None,
        "last_occurred_at": summary.last_occurred_at.isoformat() if summary.last_occurred_at is not None else None,
    }


def _node_to_public_record(node: dict[str, Any] | Any) -> dict[str, Any]:
    as_dict = node if isinstance(node, dict) else node.model_dump(mode="json")
    node_type = as_dict.get("node_type")
    record = {
        "member_type": str(node_type).lower() if isinstance(node_type, str) else "unknown",
        "name": as_dict.get("name"),
    }
    if as_dict.get("member_role") is not None:
        record["member_role"] = as_dict.get("member_role")
    if node_type == "ENTRY":
        record["entry_id"] = entry_public_id(str(as_dict.get("subject_id") or ""))
        if as_dict.get("occurred_at") is not None:
            record["occurred_at"] = as_dict.get("occurred_at")
        if as_dict.get("kind") is not None:
            record["kind"] = as_dict.get("kind")
        if as_dict.get("amount_minor") is not None:
            record["amount_minor"] = as_dict.get("amount_minor")
    elif node_type == "GROUP":
        record["group_id"] = group_public_id(str(as_dict.get("subject_id") or ""))
        if as_dict.get("group_type") is not None:
            record["group_type"] = as_dict.get("group_type")
        if as_dict.get("descendant_entry_count") is not None:
            record["descendant_entry_count"] = as_dict.get("descendant_entry_count")
        if as_dict.get("first_occurred_at") is not None or as_dict.get("last_occurred_at") is not None:
            record["date_range"] = {
                "first_occurred_at": as_dict.get("first_occurred_at"),
                "last_occurred_at": as_dict.get("last_occurred_at"),
            }
    return record


def _relationship_record(edge: dict[str, Any] | Any, node_by_graph_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    as_dict = edge if isinstance(edge, dict) else edge.model_dump(mode="json")
    source_node = node_by_graph_id.get(str(as_dict.get("source_graph_id") or ""))
    target_node = node_by_graph_id.get(str(as_dict.get("target_graph_id") or ""))
    relationship: dict[str, Any] = {
        "relation": as_dict.get("group_type"),
    }
    if source_node is not None:
        relationship["source"] = _node_to_public_record(source_node)
    if target_node is not None:
        relationship["target"] = _node_to_public_record(target_node)
    return relationship


def group_graph_to_public_record(graph: GroupGraphRead, *, full_id: bool = False) -> dict[str, Any]:
    graph_payload = graph.model_dump(mode="json")
    nodes = graph_payload.get("nodes", [])
    node_by_graph_id = {
        str(node.get("graph_id") or ""): node
        for node in nodes
        if isinstance(node, dict)
    }
    return {
        **group_summary_to_public_record(graph, full_id=full_id),
        "direct_members": [_node_to_public_record(node) for node in nodes],
        "derived_relationships": [
            _relationship_record(edge, node_by_graph_id)
            for edge in graph_payload.get("edges", [])
        ],
    }


def find_groups_by_id(db: Session, *, group_id: str, owner_user_id: str) -> list[EntryGroup]:
    normalized = group_id.strip().lower()
    if not normalized:
        return []

    exact_matches = list(
        db.scalars(
            select(EntryGroup)
            .where(
                group_owner_condition(owner_user_id),
                func.lower(EntryGroup.id) == normalized,
            )
            .options(*group_tree_options())
            .order_by(EntryGroup.created_at.asc())
        )
    )
    if exact_matches:
        return exact_matches

    return list(
        db.scalars(
            select(EntryGroup)
            .where(
                group_owner_condition(owner_user_id),
                func.lower(EntryGroup.id).like(f"{normalized}%"),
            )
            .options(*group_tree_options())
            .order_by(EntryGroup.created_at.asc())
        )
    )


def group_id_ambiguity_details(groups: list[EntryGroup], *, group_id: str) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "candidate_count": len(groups),
        "candidate_group_ids": [group.id for group in groups],
        "candidates": [
            group_summary_to_public_record(build_group_summary(group), full_id=True)
            for group in groups
        ],
    }


def group_public_summary(group: EntryGroup) -> str:
    summary = build_group_summary(group)
    return (
        f"{group_public_id(group.id)} {summary.name} {summary.group_type.value} "
        f"members={summary.direct_member_count} descendants={summary.descendant_entry_count}"
    )


def group_detail_public_record(group: EntryGroup, *, full_id: bool = False) -> dict[str, Any]:
    return group_graph_to_public_record(build_group_graph(group), full_id=full_id)
