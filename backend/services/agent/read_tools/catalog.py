# CALLING SPEC:
# - Purpose: implement focused service logic for `catalog`.
# - Inputs: callers that import `backend/services/agent/read_tools/catalog.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `catalog`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.models_finance import Account, Entity, Tag
from backend.services.agent.read_tools.common import (
    account_to_record,
    effective_entity_category,
    format_account_record,
    string_match_rank,
    tool_principal_scope,
)
from backend.services.agent.tool_args.read import ListAccountsArgs, ListEntitiesArgs, ListTagsArgs
from backend.services.agent.tool_results import format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.services.taxonomy import get_single_term_name_map


def list_tags(context: ToolContext, args: ListTagsArgs) -> ToolExecutionResult:
    _principal_name, principal_user_id, _principal_is_admin = tool_principal_scope(context)
    tags: list[Tag] = []
    if principal_user_id is not None:
        tags = list(
            context.db.scalars(
                select(Tag)
                .where(Tag.owner_user_id == principal_user_id)
                .order_by(Tag.name.asc())
            )
        )
    type_by_tag_id = get_single_term_name_map(
        context.db,
        taxonomy_key="tag_type",
        subject_type="tag",
        subject_ids=[tag.id for tag in tags],
        owner_user_id=principal_user_id or "",
    )

    ranked: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for tag in tags:
        tag_type = type_by_tag_id.get(str(tag.id))
        name_rank, name_ok = string_match_rank(tag.name, args.name)
        type_rank, type_ok = string_match_rank(tag_type, args.type)
        if not (name_ok and type_ok):
            continue
        record = {"name": tag.name, "type": tag_type, "description": tag.description}
        ranked.append(((name_rank, type_rank, tag.name.lower()), record))

    ranked.sort(key=lambda pair: pair[0])
    total_available = len(ranked)
    records = [record for _, record in ranked[: args.limit]]
    tags_text = (
        ", ".join(
            f"{tag['name']} ({tag['type'] or 'untyped'}"
            f"{'; description: ' + tag['description'] if tag.get('description') else ''})"
            for tag in records
        )
        if records
        else "(none)"
    )
    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} matching tags",
        "returned_count": len(records),
        "total_available": total_available,
        "tags": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} matching tags",
                f"tags: {tags_text}",
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )


def list_accounts(context: ToolContext, args: ListAccountsArgs) -> ToolExecutionResult:
    _principal_name, principal_user_id, _principal_is_admin = tool_principal_scope(context)

    accounts: list[Account] = []
    if principal_user_id is not None:
        conditions = [Account.owner_user_id == principal_user_id]
        if args.currency_code is not None:
            conditions.append(Account.currency_code == args.currency_code)
        if args.is_active is not None:
            conditions.append(Account.is_active.is_(args.is_active))

        accounts = list(
            context.db.scalars(
                select(Account)
                .join(Entity, Entity.id == Account.id)
                .where(*conditions)
                .options(selectinload(Account.entity))
                .order_by(func.lower(Entity.name).asc(), Account.created_at.asc())
            )
        )

    ranked: list[tuple[tuple[int, str], dict[str, Any]]] = []
    for account in accounts:
        name_rank, name_ok = string_match_rank(account.name, args.name)
        if not name_ok:
            continue
        record = account_to_record(account)
        ranked.append(((name_rank, account.name.lower()), record))

    ranked.sort(key=lambda pair: pair[0])
    total_available = len(ranked)
    records = [record for _, record in ranked[: args.limit]]
    accounts_text = "; ".join(format_account_record(record) for record in records) if records else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} matching accounts",
        "returned_count": len(records),
        "total_available": total_available,
        "accounts": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} matching accounts",
                f"accounts: {accounts_text}",
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )


def list_entities(context: ToolContext, args: ListEntitiesArgs) -> ToolExecutionResult:
    _principal_name, principal_user_id, _principal_is_admin = tool_principal_scope(context)
    entities: list[Entity] = []
    if principal_user_id is not None:
        entities = list(
            context.db.scalars(
                select(Entity)
                .outerjoin(Account, Account.id == Entity.id)
                .where(
                    Account.id.is_(None),
                    Entity.owner_user_id == principal_user_id,
                )
                .options(selectinload(Entity.account))
                .order_by(func.lower(Entity.name).asc())
            )
        )
    category_by_entity_id = get_single_term_name_map(
        context.db,
        taxonomy_key="entity_category",
        subject_type="entity",
        subject_ids=[entity.id for entity in entities],
        owner_user_id=principal_user_id or "",
    )

    ranked: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for entity in entities:
        category = effective_entity_category(entity, category_by_entity_id=category_by_entity_id)
        name_rank, name_ok = string_match_rank(entity.name, args.name)
        category_rank, category_ok = string_match_rank(category, args.category)
        if not (name_ok and category_ok):
            continue
        record = {"name": entity.name, "category": category}
        ranked.append(((name_rank, category_rank, entity.name.lower()), record))

    ranked.sort(key=lambda pair: pair[0])
    total_available = len(ranked)
    records = [record for _, record in ranked[: args.limit]]
    entities_text = "; ".join(
        f"{entity['name']} ({entity['category'] or 'uncategorized'})"
        for entity in records
    ) if records else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} matching entities",
        "returned_count": len(records),
        "total_available": total_available,
        "entities": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} matching entities",
                f"entities: {entities_text}",
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )
