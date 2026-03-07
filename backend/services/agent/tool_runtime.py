from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from backend.services.agent.tool_args import (
    INTERMEDIATE_UPDATE_TOOL_NAME,
    EmptyArgs,
    ListEntitiesArgs,
    ListEntriesArgs,
    ListTagsArgs,
    ProposeCreateEntityArgs,
    ProposeCreateEntryArgs,
    ProposeCreateTagArgs,
    ProposeDeleteEntityArgs,
    ProposeDeleteEntryArgs,
    ProposeDeleteTagArgs,
    ProposeUpdateEntityArgs,
    ProposeUpdateEntryArgs,
    ProposeUpdateTagArgs,
    RemovePendingProposalArgs,
    SendIntermediateUpdateArgs,
    UpdatePendingProposalArgs,
)
from backend.services.agent.tool_handlers_propose import (
    propose_create_entity,
    propose_create_entry,
    propose_create_tag,
    propose_delete_entity,
    propose_delete_entry,
    propose_delete_tag,
    propose_update_entity,
    propose_update_entry,
    propose_update_tag,
    remove_pending_proposal,
    update_pending_proposal,
)
from backend.services.agent.tool_handlers_read import (
    error_result,
    get_dashboard_summary,
    list_entities,
    list_entries,
    list_tags,
    send_intermediate_update,
)
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult
from backend.services.runtime_settings import resolve_runtime_settings


@dataclass(slots=True)
class AgentToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, BaseModel], ToolExecutionResult]

    @property
    def openai_tool_schema(self) -> dict[str, Any]:
        schema = _inline_local_json_schema_refs(self.args_model.model_json_schema())
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


def _inline_local_json_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or not definitions:
        return schema

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node

        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            definition_key = ref.removeprefix("#/$defs/")
            definition = definitions.get(definition_key)
            if isinstance(definition, dict):
                merged = deepcopy(definition)
                for key, value in node.items():
                    if key == "$ref":
                        continue
                    merged[key] = resolve(value)
                return resolve(merged)

        return {key: resolve(value) for key, value in node.items() if key != "$defs"}

    return resolve(schema)


TOOLS: dict[str, AgentToolDefinition] = {
    "list_entries": AgentToolDefinition(
        name="list_entries",
        description=(
            "List/query entries by date, date range, name, from_entity, to_entity, tags, and kind. "
            "When name/from/to filters are present, exact matches are ranked higher than substring matches. "
            "This tool is read-only and never mutates data."
        ),
        args_model=ListEntriesArgs,
        handler=list_entries,
    ),
    "list_tags": AgentToolDefinition(
        name="list_tags",
        description=(
            "List/query tags by name and type. Exact matches are ranked higher than substring matches. "
            "This tool is read-only and includes tag types plus tag descriptions."
        ),
        args_model=ListTagsArgs,
        handler=list_tags,
    ),
    "list_entities": AgentToolDefinition(
        name="list_entities",
        description=(
            "List/query entities by name and category. Exact matches are ranked higher than substring matches. "
            "Use category='account' when looking for account entities. This tool is read-only."
        ),
        args_model=ListEntitiesArgs,
        handler=list_entities,
    ),
    "get_dashboard_summary": AgentToolDefinition(
        name="get_dashboard_summary",
        description=(
            "Get a compact dashboard snapshot for the current month. "
            "Use this for high-level Q&A context. This tool is read-only."
        ),
        args_model=EmptyArgs,
        handler=get_dashboard_summary,
    ),
    INTERMEDIATE_UPDATE_TOOL_NAME: AgentToolDefinition(
        name=INTERMEDIATE_UPDATE_TOOL_NAME,
        description=(
            "Share a brief, user-visible progress update (supports markdown). "
            "If a task needs tool calls, call this first "
            "to describe what you are about to do before other tools. Then use sparingly for meaningful "
            "transitions between distinct tool-call batches; do not call this on every step."
        ),
        args_model=SendIntermediateUpdateArgs,
        handler=send_intermediate_update,
    ),
    "propose_create_tag": AgentToolDefinition(
        name="propose_create_tag",
        description=(
            "Create a review-gated proposal to add a new tag. "
            "This does not mutate tags immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateTagArgs,
        handler=propose_create_tag,
    ),
    "propose_update_tag": AgentToolDefinition(
        name="propose_update_tag",
        description=(
            "Create a review-gated proposal to rename a tag and/or update its type. "
            "This does not mutate tags immediately; it creates a pending review item only."
        ),
        args_model=ProposeUpdateTagArgs,
        handler=propose_update_tag,
    ),
    "propose_delete_tag": AgentToolDefinition(
        name="propose_delete_tag",
        description=(
            "Create a review-gated proposal to delete a tag. "
            "Delete behavior removes tag links from affected entries; it does not delete entries. "
            "This does not mutate tags immediately; it creates a pending review item only."
        ),
        args_model=ProposeDeleteTagArgs,
        handler=propose_delete_tag,
    ),
    "propose_create_entity": AgentToolDefinition(
        name="propose_create_entity",
        description=(
            "Create a review-gated proposal to add a new entity. "
            "This does not mutate entities immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateEntityArgs,
        handler=propose_create_entity,
    ),
    "propose_update_entity": AgentToolDefinition(
        name="propose_update_entity",
        description=(
            "Create a review-gated proposal to rename an entity and/or update its category. "
            "This does not mutate entities immediately; it creates a pending review item only."
        ),
        args_model=ProposeUpdateEntityArgs,
        handler=propose_update_entity,
    ),
    "propose_delete_entity": AgentToolDefinition(
        name="propose_delete_entity",
        description=(
            "Create a review-gated proposal to delete an entity. "
            "Delete behavior preserves denormalized entry labels while detaching nullable references; "
            "account-backed entities must be managed from Accounts."
        ),
        args_model=ProposeDeleteEntityArgs,
        handler=propose_delete_entity,
    ),
    "propose_create_entry": AgentToolDefinition(
        name="propose_create_entry",
        description=(
            "Create a review-gated proposal to add a new entry. "
            "This does not mutate entries immediately; it creates a pending review item only. "
            "from_entity/to_entity may reference existing entities or pending create_entity proposals "
            "already in the current thread. "
            "When markdown_notes is provided, keep it human-readable markdown that preserves all relevant "
            "input details. For short notes, avoid headings; prefer clear line breaks and ordered/unordered lists."
        ),
        args_model=ProposeCreateEntryArgs,
        handler=propose_create_entry,
    ),
    "propose_update_entry": AgentToolDefinition(
        name="propose_update_entry",
        description=(
            "Create a review-gated proposal to update an existing entry selected by date/amount/name/from/to. "
            "If selector matches multiple entries, the tool reports ambiguity so the user can clarify. "
            "When patch.markdown_notes is provided, keep it human-readable markdown that preserves all relevant "
            "input details. For short notes, avoid headings; prefer clear line breaks and ordered/unordered lists."
        ),
        args_model=ProposeUpdateEntryArgs,
        handler=propose_update_entry,
    ),
    "propose_delete_entry": AgentToolDefinition(
        name="propose_delete_entry",
        description=(
            "Create a review-gated proposal to delete an existing entry selected by date/amount/name/from/to. "
            "If selector matches multiple entries, the tool reports ambiguity so the user can clarify."
        ),
        args_model=ProposeDeleteEntryArgs,
        handler=propose_delete_entry,
    ),
    "update_pending_proposal": AgentToolDefinition(
        name="update_pending_proposal",
        description=(
            "Update a pending review proposal by proposal_id using a patch_map of field paths to new values. "
            "Only pending proposals in the current thread are mutable."
        ),
        args_model=UpdatePendingProposalArgs,
        handler=update_pending_proposal,
    ),
    "remove_pending_proposal": AgentToolDefinition(
        name="remove_pending_proposal",
        description=(
            "Remove a pending review proposal by proposal_id from the current thread's pending proposal pool. "
            "Use this when the user asks to discard/cancel a pending proposal."
        ),
        args_model=RemovePendingProposalArgs,
        handler=remove_pending_proposal,
    ),
}


def build_openai_tool_schemas() -> list[dict[str, Any]]:
    return [tool.openai_tool_schema for tool in TOOLS.values()]


def execute_tool(name: str, arguments: dict[str, Any], context: ToolContext) -> ToolExecutionResult:
    definition = TOOLS.get(name)
    if definition is None:
        return error_result(f"unknown tool '{name}'")

    try:
        parsed = definition.args_model.model_validate(arguments)
    except ValidationError as exc:
        return error_result("invalid tool arguments", details=exc.errors())

    settings = resolve_runtime_settings(context.db)
    retrying = Retrying(
        stop=stop_after_attempt(settings.agent_retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.agent_retry_initial_wait_seconds,
            max=settings.agent_retry_max_wait_seconds,
            exp_base=settings.agent_retry_backoff_multiplier,
        ),
        retry=retry_if_exception(lambda exc: not isinstance(exc, ValueError)),
        reraise=True,
    )

    try:
        result = None
        for attempt in retrying:
            with attempt:
                result = definition.handler(context, parsed)
        if result is None:  # pragma: no cover - defensive guard
            return error_result("tool execution failed", details="no result returned")
        return result
    except ValueError as exc:
        return error_result("tool execution failed", details=str(exc))
    except Exception as exc:  # pragma: no cover - guarded for runtime resilience
        return error_result("tool execution failed", details=str(exc))
