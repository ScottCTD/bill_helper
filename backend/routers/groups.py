from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal, get_current_principal
from backend.database import get_db
from backend.models_finance import Entry, EntryLink
from backend.schemas_finance import GroupEdge, GroupGraphRead, GroupNode, GroupSummaryRead
from backend.services.access_scope import entry_owner_filter

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=list[GroupSummaryRead])
def list_group_summaries(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[GroupSummaryRead]:
    entries = list(
        db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                entry_owner_filter(principal),
            )
            .order_by(Entry.occurred_at.asc(), Entry.created_at.asc())
        )
    )
    if not entries:
        return []

    group_entries: dict[str, list[Entry]] = defaultdict(list)
    entry_group_by_id: dict[str, str] = {}
    for entry in entries:
        group_entries[entry.group_id].append(entry)
        entry_group_by_id[entry.id] = entry.group_id

    active_entry_ids = set(entry_group_by_id.keys())
    edge_counts = defaultdict(int)
    links = list(
        db.scalars(
            select(EntryLink).where(
                EntryLink.source_entry_id.in_(active_entry_ids),
                EntryLink.target_entry_id.in_(active_entry_ids),
            )
        )
    )
    for link in links:
        source_group_id = entry_group_by_id.get(link.source_entry_id)
        target_group_id = entry_group_by_id.get(link.target_entry_id)
        if source_group_id is not None and source_group_id == target_group_id:
            edge_counts[source_group_id] += 1

    summaries: list[GroupSummaryRead] = []
    for group_id, grouped_entries in group_entries.items():
        if len(grouped_entries) < 2:
            continue
        latest_entry = max(grouped_entries, key=lambda entry: (entry.occurred_at, entry.created_at))
        summaries.append(
            GroupSummaryRead(
                group_id=group_id,
                entry_count=len(grouped_entries),
                edge_count=edge_counts.get(group_id, 0),
                first_occurred_at=min(entry.occurred_at for entry in grouped_entries),
                last_occurred_at=max(entry.occurred_at for entry in grouped_entries),
                latest_entry_name=latest_entry.name,
            )
        )

    return sorted(
        summaries,
        key=lambda summary: (
            summary.last_occurred_at,
            summary.entry_count,
            summary.group_id,
        ),
        reverse=True,
    )


@router.get("/{group_id}", response_model=GroupGraphRead)
def get_group_graph(
    group_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> GroupGraphRead:
    entries = list(
        db.scalars(
            select(Entry)
            .where(
                Entry.group_id == group_id,
                Entry.is_deleted.is_(False),
                entry_owner_filter(principal),
            )
            .order_by(Entry.occurred_at.asc(), Entry.created_at.asc())
        )
    )
    if not entries:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    entry_ids = [entry.id for entry in entries]
    edges = list(
        db.scalars(
            select(EntryLink)
            .where(EntryLink.source_entry_id.in_(entry_ids), EntryLink.target_entry_id.in_(entry_ids))
            .order_by(EntryLink.created_at.asc())
        )
    )

    return GroupGraphRead(
        group_id=group_id,
        nodes=[
            GroupNode(
                id=entry.id,
                name=entry.name,
                kind=entry.kind,
                amount_minor=entry.amount_minor,
                occurred_at=entry.occurred_at,
            )
            for entry in entries
        ],
        edges=[
            GroupEdge(
                id=edge.id,
                source_entry_id=edge.source_entry_id,
                target_entry_id=edge.target_entry_id,
                link_type=edge.link_type,
                note=edge.note,
            )
            for edge in edges
        ],
    )
