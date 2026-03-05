from __future__ import annotations

from backend.models_finance import Entry, EntryLink, Tag
from backend.schemas_finance import EntryDetailRead, EntryRead, LinkRead, TagRead


def tag_to_schema(tag: Tag) -> TagRead:
    return TagRead(id=tag.id, name=tag.name, color=tag.color, description=tag.description)


def link_to_schema(link: EntryLink) -> LinkRead:
    return LinkRead(
        id=link.id,
        source_entry_id=link.source_entry_id,
        target_entry_id=link.target_entry_id,
        link_type=link.link_type,
        note=link.note,
        created_at=link.created_at,
    )


def entry_to_schema(entry: Entry) -> EntryRead:
    return EntryRead(
        id=entry.id,
        group_id=entry.group_id,
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
        to_entity=entry.to_entity,
        owner=entry.owner,
        markdown_body=entry.markdown_body,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        tags=[tag_to_schema(tag) for tag in entry.tags],
    )


def entry_to_detail_schema(entry: Entry, links: list[EntryLink]) -> EntryDetailRead:
    return EntryDetailRead(
        **entry_to_schema(entry).model_dump(),
        links=[link_to_schema(link) for link in links],
    )
