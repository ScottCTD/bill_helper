from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Entry, EntryLink
from backend.schemas import GroupEdge, GroupGraphRead, GroupNode

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("/{group_id}", response_model=GroupGraphRead)
def get_group_graph(group_id: str, db: Session = Depends(get_db)) -> GroupGraphRead:
    entries = list(
        db.scalars(
            select(Entry)
            .where(Entry.group_id == group_id, Entry.is_deleted.is_(False))
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
