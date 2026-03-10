from __future__ import annotations

from backend.models_finance import Entry, EntryGroup, Tag
from backend.schemas_finance import EntryDetailRead, EntryGroupRefRead, EntryRead, TagSummaryRead


def tag_to_summary(tag: Tag) -> TagSummaryRead:
    return TagSummaryRead(id=tag.id, name=tag.name, color=tag.color, description=tag.description)


def group_to_ref(group: EntryGroup) -> EntryGroupRefRead:
    return EntryGroupRefRead(
        id=group.id,
        name=group.name,
        group_type=group.group_type,
    )


def build_entry_group_path(entry: Entry) -> list[EntryGroupRefRead]:
    membership = entry.group_membership
    if membership is None or membership.group is None:
        return []

    direct_group = membership.group
    if direct_group.parent_membership is None or direct_group.parent_membership.group is None:
        return [group_to_ref(direct_group)]

    return [
        group_to_ref(direct_group.parent_membership.group),
        group_to_ref(direct_group),
    ]


def entry_to_schema(entry: Entry) -> EntryRead:
    from_entity_missing = bool(entry.from_entity and entry.from_entity_id is None)
    to_entity_missing = bool(entry.to_entity and entry.to_entity_id is None)
    group_path = build_entry_group_path(entry)
    direct_group = group_path[-1] if group_path else None
    return EntryRead(
        id=entry.id,
        account_id=entry.account_id,
        kind=entry.kind,
        occurred_at=entry.occurred_at,
        name=entry.name,
        amount_minor=entry.amount_minor,
        currency_code=entry.currency_code,
        from_entity_id=entry.from_entity_id,
        to_entity_id=entry.to_entity_id,
        owner_user_id=entry.owner_user_id,
        from_entity=entry.from_entity,
        from_entity_missing=from_entity_missing,
        to_entity=entry.to_entity,
        to_entity_missing=to_entity_missing,
        owner=entry.owner,
        markdown_body=entry.markdown_body,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        tags=[tag_to_summary(tag) for tag in entry.tags],
        direct_group=direct_group,
        direct_group_member_role=entry.group_membership.member_role if entry.group_membership is not None else None,
        group_path=group_path,
    )


def entry_to_detail_schema(entry: Entry) -> EntryDetailRead:
    return EntryDetailRead(**entry_to_schema(entry).model_dump())
