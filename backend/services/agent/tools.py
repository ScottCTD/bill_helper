from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.enums import AgentChangeStatus, AgentChangeType
from backend.models import Account, AgentChangeItem, Entity, Entry, Tag
from backend.services.entries import normalize_tag_name
from backend.services.finance import aggregate_monthly_totals, aggregate_top_tags, month_window


@dataclass(slots=True)
class ToolExecutionResult:
    output_text: str
    output_json: dict[str, Any]
    status: str


@dataclass(slots=True)
class ToolContext:
    db: Session
    run_id: str


@dataclass(slots=True)
class AgentToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, BaseModel], ToolExecutionResult]

    @property
    def openai_tool_schema(self) -> dict[str, Any]:
        schema = self.args_model.model_json_schema()
        schema.pop("$defs", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


class EmptyArgs(BaseModel):
    pass


class SearchEntriesArgs(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1)


class ListEntriesArgs(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    limit: int = Field(default=50, ge=1)


class ListTagsArgs(BaseModel):
    query: str | None = None


class ListEntitiesArgs(BaseModel):
    query: str | None = None


class ProposeCreateTagArgs(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=20)
    rationale: str = Field(min_length=1, max_length=500)


class ProposeCreateEntityArgs(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    rationale: str = Field(min_length=1, max_length=500)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip().lower()
        return normalized or None


class ProposeCreateEntryArgs(BaseModel):
    kind: str = Field(pattern="^(EXPENSE|INCOME)$")
    occurred_at: date
    name: str = Field(min_length=1, max_length=255)
    amount_minor: int = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    account_id: str | None = None
    from_entity_id: str | None = None
    to_entity_id: str | None = None
    from_entity: str | None = Field(default=None, max_length=255)
    to_entity: str | None = Field(default=None, max_length=255)
    owner_user_id: str | None = None
    owner: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    markdown_body: str | None = None
    rationale: str = Field(min_length=1, max_length=1000)
    duplicate_check_note: str | None = Field(default=None, max_length=1000)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


def _entry_compact(entry: Entry) -> str:
    return (
        f"{entry.id[:8]} {entry.occurred_at.isoformat()} "
        f"{entry.name} {entry.amount_minor} {entry.currency_code}"
    )


def _format_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def _search_entries(context: ToolContext, args: SearchEntriesArgs) -> ToolExecutionResult:
    query = args.query.strip()
    pattern = f"%{query}%"
    rows = list(
        context.db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                or_(
                    Entry.name.ilike(pattern),
                    Entry.from_entity.ilike(pattern),
                    Entry.to_entity.ilike(pattern),
                ),
            )
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
            .limit(args.limit)
        )
    )
    entries_text = "; ".join(_entry_compact(entry) for entry in rows) if rows else "(none)"
    output_json = {
        "status": "OK",
        "summary": f'found {len(rows)} entries for query "{query}"',
        "entries": [
            {
                "id": entry.id,
                "occurred_at": entry.occurred_at.isoformat(),
                "name": entry.name,
                "amount_minor": entry.amount_minor,
                "currency_code": entry.currency_code,
            }
            for entry in rows
        ],
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f'summary: found {len(rows)} entries for query "{query}"',
                f"entries: {entries_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _list_entries(context: ToolContext, args: ListEntriesArgs) -> ToolExecutionResult:
    conditions = [Entry.is_deleted.is_(False)]
    if args.start_date is not None:
        conditions.append(Entry.occurred_at >= args.start_date)
    if args.end_date is not None:
        conditions.append(Entry.occurred_at <= args.end_date)
    rows = list(
        context.db.scalars(
            select(Entry)
            .where(*conditions)
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
            .limit(args.limit)
        )
    )
    entries_text = "; ".join(_entry_compact(entry) for entry in rows) if rows else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"found {len(rows)} entries in date range",
        "entries": [
            {
                "id": entry.id,
                "occurred_at": entry.occurred_at.isoformat(),
                "name": entry.name,
                "amount_minor": entry.amount_minor,
                "currency_code": entry.currency_code,
            }
            for entry in rows
        ],
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: found {len(rows)} entries in date range",
                f"entries: {entries_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _list_tags(context: ToolContext, args: ListTagsArgs) -> ToolExecutionResult:
    stmt = select(Tag).order_by(Tag.name.asc())
    query = args.query.strip().lower() if args.query else None
    if query:
        stmt = stmt.where(func.lower(Tag.name).contains(query))
    rows = list(context.db.scalars(stmt))
    names = [tag.name for tag in rows]
    tags_text = ", ".join(names) if names else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"found {len(rows)} tags",
        "tags": names,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: found {len(rows)} tags",
                f"tags: {tags_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _list_entities(context: ToolContext, args: ListEntitiesArgs) -> ToolExecutionResult:
    stmt = select(Entity).order_by(func.lower(Entity.name).asc())
    query = args.query.strip().lower() if args.query else None
    if query:
        stmt = stmt.where(func.lower(Entity.name).contains(query))
    rows = list(context.db.scalars(stmt))
    entities_text = (
        "; ".join(
            f"{entity.id[:8]} {entity.name}{f' ({entity.category})' if entity.category else ''}" for entity in rows
        )
        if rows
        else "(none)"
    )
    output_json = {
        "status": "OK",
        "summary": f"found {len(rows)} entities",
        "entities": [
            {"id": entity.id, "name": entity.name, "category": entity.category}
            for entity in rows
        ],
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: found {len(rows)} entities",
                f"entities: {entities_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _list_accounts(context: ToolContext, _: EmptyArgs) -> ToolExecutionResult:
    rows = list(
        context.db.scalars(
            select(Account)
            .where(Account.is_active.is_(True))
            .order_by(func.lower(Account.name).asc())
        )
    )
    accounts_text = "; ".join(f"{account.id[:8]} {account.name} {account.currency_code}" for account in rows) if rows else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"found {len(rows)} active accounts",
        "accounts": [
            {"id": account.id, "name": account.name, "currency_code": account.currency_code}
            for account in rows
        ],
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: found {len(rows)} active accounts",
                f"accounts: {accounts_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _get_dashboard_summary(context: ToolContext, _: EmptyArgs) -> ToolExecutionResult:
    month = date.today().strftime("%Y-%m")
    start, end = month_window(month)
    expenses, incomes = aggregate_monthly_totals(context.db, start, end)
    top_tags = aggregate_top_tags(context.db, start, end, limit=5)
    top_tags_text = "; ".join(f"{item.tag}:{item.currency_code}:{item.total_minor}" for item in top_tags) if top_tags else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"dashboard snapshot for {month}",
        "expenses_by_currency": expenses,
        "incomes_by_currency": incomes,
        "top_tags": [
            {"tag": item.tag, "currency_code": item.currency_code, "total_minor": item.total_minor}
            for item in top_tags
        ],
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: dashboard snapshot for {month}",
                f"expenses_by_currency: {expenses}",
                f"incomes_by_currency: {incomes}",
                f"top_tags: {top_tags_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _propose_create_tag(context: ToolContext, args: ProposeCreateTagArgs) -> ToolExecutionResult:
    normalized_name = normalize_tag_name(args.name)
    payload = {"name": normalized_name, "color": args.color}
    item = AgentChangeItem(
        run_id=context.run_id,
        change_type=AgentChangeType.CREATE_TAG,
        payload_json=payload,
        rationale_text=args.rationale.strip(),
        status=AgentChangeStatus.PENDING_REVIEW,
    )
    context.db.add(item)
    context.db.flush()
    output_json = {
        "status": "OK",
        "summary": "proposed tag creation",
        "change_item_id": item.id,
        "item_status": item.status.value,
        "preview": payload,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                "summary: proposed tag creation",
                f"change_item_id: {item.id}",
                f"status: {item.status.value}",
                f"preview: {payload}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _propose_create_entity(context: ToolContext, args: ProposeCreateEntityArgs) -> ToolExecutionResult:
    payload = {"name": " ".join(args.name.split()).strip(), "category": args.category}
    item = AgentChangeItem(
        run_id=context.run_id,
        change_type=AgentChangeType.CREATE_ENTITY,
        payload_json=payload,
        rationale_text=args.rationale.strip(),
        status=AgentChangeStatus.PENDING_REVIEW,
    )
    context.db.add(item)
    context.db.flush()
    output_json = {
        "status": "OK",
        "summary": "proposed entity creation",
        "change_item_id": item.id,
        "item_status": item.status.value,
        "preview": payload,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                "summary: proposed entity creation",
                f"change_item_id: {item.id}",
                f"status: {item.status.value}",
                f"preview: {payload}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _propose_create_entry(context: ToolContext, args: ProposeCreateEntryArgs) -> ToolExecutionResult:
    payload = args.model_dump(exclude={"rationale", "duplicate_check_note"})
    payload["occurred_at"] = args.occurred_at.isoformat()
    payload["tags"] = [normalize_tag_name(tag) for tag in payload.get("tags", []) if tag.strip()]
    item = AgentChangeItem(
        run_id=context.run_id,
        change_type=AgentChangeType.CREATE_ENTRY,
        payload_json=payload,
        rationale_text=args.rationale.strip(),
        status=AgentChangeStatus.PENDING_REVIEW,
        review_note=args.duplicate_check_note,
    )
    context.db.add(item)
    context.db.flush()
    preview = {
        "occurred_at": payload["occurred_at"],
        "kind": payload["kind"],
        "name": payload["name"],
        "amount_minor": payload["amount_minor"],
        "currency_code": payload["currency_code"],
        "tags": payload["tags"],
    }
    output_json = {
        "status": "OK",
        "summary": "proposed entry creation",
        "change_item_id": item.id,
        "item_status": item.status.value,
        "preview": preview,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                "summary: proposed entry creation",
                f"change_item_id: {item.id}",
                f"status: {item.status.value}",
                f"preview: {preview}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


TOOLS: dict[str, AgentToolDefinition] = {
    "search_entries": AgentToolDefinition(
        name="search_entries",
        description=(
            "Search entries by free-text query across name/from/to fields. "
            "Use this for factual Q&A and duplicate checks before proposing new entries. "
            "This tool is read-only and never mutates data."
        ),
        args_model=SearchEntriesArgs,
        handler=_search_entries,
    ),
    "list_entries": AgentToolDefinition(
        name="list_entries",
        description=(
            "List entries using a basic date-range filter. "
            "Use this for recent activity and timeline inspection. "
            "This tool is read-only and never mutates data."
        ),
        args_model=ListEntriesArgs,
        handler=_list_entries,
    ),
    "list_tags": AgentToolDefinition(
        name="list_tags",
        description=(
            "List tags for grounding and reuse. "
            "Prefer an existing tag before proposing a new one. This tool is read-only."
        ),
        args_model=ListTagsArgs,
        handler=_list_tags,
    ),
    "list_entities": AgentToolDefinition(
        name="list_entities",
        description=(
            "List entities for grounding and reuse. "
            "Prefer an existing entity before proposing a new one. This tool is read-only."
        ),
        args_model=ListEntitiesArgs,
        handler=_list_entities,
    ),
    "list_accounts": AgentToolDefinition(
        name="list_accounts",
        description="List active accounts for entry context. This tool is read-only.",
        args_model=EmptyArgs,
        handler=_list_accounts,
    ),
    "get_dashboard_summary": AgentToolDefinition(
        name="get_dashboard_summary",
        description=(
            "Get a compact dashboard snapshot for the current month. "
            "Use this for high-level Q&A context. This tool is read-only."
        ),
        args_model=EmptyArgs,
        handler=_get_dashboard_summary,
    ),
    "propose_create_tag": AgentToolDefinition(
        name="propose_create_tag",
        description=(
            "Create a review-gated proposal to add a new tag. "
            "This does not create the tag immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateTagArgs,
        handler=_propose_create_tag,
    ),
    "propose_create_entity": AgentToolDefinition(
        name="propose_create_entity",
        description=(
            "Create a review-gated proposal to add a new entity. "
            "This does not create the entity immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateEntityArgs,
        handler=_propose_create_entity,
    ),
    "propose_create_entry": AgentToolDefinition(
        name="propose_create_entry",
        description=(
            "Create a review-gated proposal to add a new ledger entry. "
            "This does not create the entry immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateEntryArgs,
        handler=_propose_create_entry,
    ),
}


def build_openai_tool_schemas() -> list[dict[str, Any]]:
    return [tool.openai_tool_schema for tool in TOOLS.values()]


def execute_tool(name: str, arguments: dict[str, Any], context: ToolContext) -> ToolExecutionResult:
    definition = TOOLS.get(name)
    if definition is None:
        return ToolExecutionResult(
            output_text=_format_lines(["ERROR", f"summary: unknown tool '{name}'"]),
            output_json={"status": "ERROR", "summary": f"unknown tool '{name}'"},
            status="error",
        )

    try:
        parsed = definition.args_model.model_validate(arguments)
    except ValidationError as exc:
        return ToolExecutionResult(
            output_text=_format_lines(["ERROR", "summary: invalid tool arguments", f"details: {exc.errors()}"]),
            output_json={"status": "ERROR", "summary": "invalid tool arguments", "errors": exc.errors()},
            status="error",
        )

    try:
        return definition.handler(context, parsed)
    except Exception as exc:  # pragma: no cover - guarded for runtime resilience
        return ToolExecutionResult(
            output_text=_format_lines(["ERROR", "summary: tool execution failed", f"details: {str(exc)}"]),
            output_json={"status": "ERROR", "summary": "tool execution failed", "details": str(exc)},
            status="error",
        )
