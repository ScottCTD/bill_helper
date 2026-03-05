from __future__ import annotations

from collections import defaultdict
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models_finance import Entry, EntryGroup, EntryLink


def _new_group_id() -> str:
    return str(uuid4())


def assign_initial_group(db: Session, entry: Entry) -> None:
    group = EntryGroup()
    db.add(group)
    db.flush()
    entry.group_id = group.id


def recompute_entry_groups(db: Session) -> None:
    """
    Recompute connected components across all active entries and reassign group IDs.
    """
    entries = list(db.scalars(select(Entry).where(Entry.is_deleted.is_(False))))
    if not entries:
        return

    entry_by_id = {entry.id: entry for entry in entries}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for entry_id in entry_by_id:
        adjacency[entry_id]

    links = list(db.scalars(select(EntryLink)))
    for link in links:
        if link.source_entry_id in entry_by_id and link.target_entry_id in entry_by_id:
            adjacency[link.source_entry_id].add(link.target_entry_id)
            adjacency[link.target_entry_id].add(link.source_entry_id)

    visited: set[str] = set()
    components: list[list[str]] = []

    for entry_id in entry_by_id:
        if entry_id in visited:
            continue
        stack = [entry_id]
        component: list[str] = []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            stack.extend(neighbor for neighbor in adjacency[node] if neighbor not in visited)
        components.append(component)

    used_group_ids: set[str] = set()
    touched_group_ids: set[str] = set()

    for component in components:
        existing_group_ids = sorted(
            {
                entry_by_id[entry_id].group_id
                for entry_id in component
                if entry_by_id[entry_id].group_id is not None
            }
        )
        selected_group_id = next((gid for gid in existing_group_ids if gid not in used_group_ids), None)
        if selected_group_id is None:
            selected_group_id = _new_group_id()

        if db.get(EntryGroup, selected_group_id) is None:
            db.add(EntryGroup(id=selected_group_id))

        used_group_ids.add(selected_group_id)
        touched_group_ids.add(selected_group_id)

        for entry_id in component:
            entry_by_id[entry_id].group_id = selected_group_id

    for group_id in touched_group_ids:
        group = db.get(EntryGroup, group_id)
        if group is not None:
            db.add(group)

    db.flush()
