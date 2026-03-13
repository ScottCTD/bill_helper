# CALLING SPEC:
# - Purpose: implement focused service logic for `common`.
# - Inputs: callers that import `backend/services/agent/read_tools/common.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `common`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models_finance import Account, Entity, Entry
from backend.services.agent.group_references import (
    GroupMemberPublicRecord,
    GroupRelationshipRecord,
)
from backend.services.agent.payload_normalization import normalize_loose_text
from backend.services.agent.principal_scope import load_run_principal
from backend.services.agent.user_context import normalize_account_markdown_for_context
from backend.services.agent.tool_types import ToolContext


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


def _load_run_principal(context: ToolContext) -> tuple[str | None, str | None, bool]:
    principal = load_run_principal(context.db, run_id=context.run_id)
    if principal is None:
        return None, None, False
    return principal.user_name, principal.user_id, principal.is_admin


def tool_principal_scope(context: ToolContext) -> tuple[str | None, str | None, bool]:
    if (
        context.principal_name is not None
        or context.principal_user_id is not None
        or context.principal_is_admin is not None
    ):
        return context.principal_name, context.principal_user_id, bool(context.principal_is_admin)
    return _load_run_principal(context)


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
        "account_id": account.id,
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
        f"account_id={record.get('account_id')} {record.get('name')} ({record.get('currency_code')}; "
        f"{'active' if record.get('is_active') else 'inactive'}{notes_text})"
    )


def get_account_by_id_for_tool_context(context: ToolContext, account_id: str) -> Account | None:
    _principal_name, principal_user_id, _principal_is_admin = tool_principal_scope(context)
    if principal_user_id is None:
        return None

    return context.db.scalar(
        select(Account)
        .join(Entity, Entity.id == Account.id)
        .where(
            Account.id == account_id,
            Account.owner_user_id == principal_user_id,
        )
        .options(selectinload(Account.entity))
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
