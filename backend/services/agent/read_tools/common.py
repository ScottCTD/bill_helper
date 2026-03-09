from __future__ import annotations

from typing import Any

from backend.models_finance import Account, Entity, Entry
from backend.services.agent.group_references import (
    GroupMemberPublicRecord,
    GroupRelationshipRecord,
)
from backend.services.agent.payload_normalization import normalize_loose_text
from backend.services.agent.user_context import normalize_account_markdown_for_context
from backend.services.agent.tool_types import ToolContext
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.users import find_user_by_name


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


def tool_principal_scope(context: ToolContext) -> tuple[str, str | None]:
    if context.principal_name is not None:
        return context.principal_name, context.principal_user_id
    settings = resolve_runtime_settings(context.db)
    principal_name = settings.current_user_name
    principal_user = find_user_by_name(context.db, principal_name)
    return principal_name, principal_user.id if principal_user is not None else None
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


def format_entry_record(record: dict[str, Any]) -> str:
    tags = record.get("tags") or []
    return (
        f"entry_id={record.get('entry_id')} {record.get('date')} {record.get('name')} "
        f"{record.get('amount_minor')} {record.get('currency_code')} "
        f"from={record.get('from_entity') or '-'} to={record.get('to_entity') or '-'} tags={tags}"
    )


def account_to_record(account: Account) -> dict[str, Any]:
    return {
        "name": account.name,
        "currency_code": account.currency_code,
        "is_active": account.is_active,
        "markdown_body": normalize_account_markdown_for_context(account.markdown_body),
    }


def format_account_record(record: dict[str, Any]) -> str:
    notes = record.get("markdown_body")
    if isinstance(notes, str):
        notes = " / ".join(line.strip() for line in notes.splitlines() if line.strip())
    notes_text = f"; notes: {notes}" if notes else ""
    return (
        f"{record.get('name')} ({record.get('currency_code')}; "
        f"{'active' if record.get('is_active') else 'inactive'}{notes_text})"
    )


def format_group_member_record(record: GroupMemberPublicRecord | dict[str, Any]) -> str:
    member_type = record.get("member_type")
    member_role = f" role={record.get('member_role')}" if record.get("member_role") else ""
    if member_type == "entry":
        return (
            f"entry_id={record.get('entry_id')} {record.get('occurred_at')} {record.get('name')} "
            f"{record.get('amount_minor')} {record.get('kind')}{member_role}"
        )
    date_range = record.get("date_range") or {}
    return (
        f"group_id={record.get('group_id')} {record.get('name')} ({record.get('group_type')}, "
        f"descendants={record.get('descendant_entry_count')}, "
        f"range={date_range.get('first_occurred_at') or '-'} to {date_range.get('last_occurred_at') or '-'}){member_role}"
    )


def format_group_relationship_record(record: GroupRelationshipRecord | dict[str, Any]) -> str:
    source = record.get("source") or {}
    target = record.get("target") or {}
    source_id = source.get("entry_id") or source.get("group_id") or "?"
    target_id = target.get("entry_id") or target.get("group_id") or "?"
    source_name = source.get("name") or "Unknown"
    target_name = target.get("name") or "Unknown"
    return f"{source_id} {source_name} -> {target_id} {target_name} ({record.get('relation')})"
