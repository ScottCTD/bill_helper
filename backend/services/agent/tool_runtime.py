from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from backend.services.agent.change_contracts import (
    CreateAccountPayload as ProposeCreateAccountArgs,
    CreateEntityPayload as ProposeCreateEntityArgs,
    CreateEntryPayload as ProposeCreateEntryArgs,
    CreateGroupPayload as ProposeCreateGroupArgs,
    CreateTagPayload as ProposeCreateTagArgs,
    DeleteAccountPayload as ProposeDeleteAccountArgs,
    DeleteEntityPayload as ProposeDeleteEntityArgs,
    DeleteEntryPayload as ProposeDeleteEntryArgs,
    DeleteGroupPayload as ProposeDeleteGroupArgs,
    DeleteTagPayload as ProposeDeleteTagArgs,
    UpdateAccountPayload as ProposeUpdateAccountArgs,
    UpdateEntityPayload as ProposeUpdateEntityArgs,
    UpdateEntryPayload as ProposeUpdateEntryArgs,
    UpdateGroupPayload as ProposeUpdateGroupArgs,
    UpdateTagPayload as ProposeUpdateTagArgs,
)
from backend.services.agent.tool_args import (
    AddUserMemoryArgs,
    INTERMEDIATE_UPDATE_TOOL_NAME,
    ListAccountsArgs,
    ListEntitiesArgs,
    ListEntriesArgs,
    ListGroupsArgs,
    ListProposalsArgs,
    ListTagsArgs,
    ProposeUpdateGroupMembershipArgs,
    RenameThreadArgs,
    RemovePendingProposalArgs,
    SendIntermediateUpdateArgs,
    UpdatePendingProposalArgs,
)
from backend.services.agent.tool_handlers_memory import add_user_memory
from backend.services.agent.tool_handlers_propose import (
    propose_create_account,
    propose_create_entity,
    propose_create_entry,
    propose_create_group,
    propose_create_tag,
    propose_delete_account,
    propose_delete_entity,
    propose_delete_entry,
    propose_delete_group,
    propose_delete_tag,
    propose_update_account,
    propose_update_entity,
    propose_update_entry,
    propose_update_group,
    propose_update_group_membership,
    propose_update_tag,
    remove_pending_proposal,
    update_pending_proposal,
)
from backend.services.agent.tool_handlers_read import (
    error_result,
    list_accounts,
    list_entities,
    list_entries,
    list_groups,
    list_proposals,
    list_tags,
    send_intermediate_update,
)
from backend.services.agent.tool_handlers_threads import rename_thread
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
            "List/query entries by date, date range, source, name, from_entity, to_entity, tags, and kind. "
            "Use source for broad text search across entry name, from_entity, and to_entity, matching the Entries table search. "
            "When source/name/from/to filters are present, exact matches are ranked higher than substring matches. "
            "Each returned entry includes an entry_id alias you can reuse in propose_update_entry "
            "or propose_delete_entry. This tool is read-only and never mutates data."
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
    "list_accounts": AgentToolDefinition(
        name="list_accounts",
        description=(
            "List/query accounts by name, currency_code, and active status. "
            "Use this for account discovery, account edits, and account deletions. "
            "Returned records include name, currency_code, is_active, and compact markdown_body notes. "
            "This tool is read-only."
        ),
        args_model=ListAccountsArgs,
        handler=list_accounts,
    ),
    "list_entities": AgentToolDefinition(
        name="list_entities",
        description=(
            "List/query entities by name and category. Exact matches are ranked higher than substring matches. "
            "Use this for non-account counterparties and categories. This tool is read-only."
        ),
        args_model=ListEntitiesArgs,
        handler=list_entities,
    ),
    "list_groups": AgentToolDefinition(
        name="list_groups",
        description=(
            "List/query entry groups by name or group_type, or inspect one group in detail with group_id. "
            "In list mode, each returned row includes a reusable group_id alias. "
            "In detail mode, provide only group_id and this tool returns the selected group's summary, "
            "direct members, and compact derived relationships. This tool is read-only."
        ),
        args_model=ListGroupsArgs,
        handler=list_groups,
    ),
    "list_proposals": AgentToolDefinition(
        name="list_proposals",
        description=(
            "List proposals in the current thread by proposal type, CRUD action, lifecycle status, "
            "or optional proposal_id. Use this to inspect pending, rejected, applied, or failed proposals "
            "before revising, removing, or explaining proposal history. This tool is read-only."
        ),
        args_model=ListProposalsArgs,
        handler=list_proposals,
    ),
    "add_user_memory": AgentToolDefinition(
        name="add_user_memory",
        description=(
            "Append new persistent user-memory items. Use this only when the user clearly asks you "
            "to remember/store a standing preference, rule, or hint for future runs. This tool is "
            "add-only: do not use it to mutate or remove existing memory."
        ),
        args_model=AddUserMemoryArgs,
        handler=add_user_memory,
    ),
    "rename_thread": AgentToolDefinition(
        name="rename_thread",
        description=(
            "Rename the current thread to a short 1-5 word topic. Use this right after the first user "
            "message in a new thread. After that, only rename when the user explicitly asks or the topic "
            "shifts substantially."
        ),
        args_model=RenameThreadArgs,
        handler=rename_thread,
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
            "This does not mutate entities immediately; it creates a pending review item only. "
            "Do not use this for accounts; accounts must be managed with account proposal tools."
        ),
        args_model=ProposeCreateEntityArgs,
        handler=propose_create_entity,
    ),
    "propose_update_entity": AgentToolDefinition(
        name="propose_update_entity",
        description=(
            "Create a review-gated proposal to rename an entity and/or update its category. "
            "This does not mutate entities immediately; it creates a pending review item only. "
            "Do not use this for accounts; accounts must be managed with account proposal tools."
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
    "propose_create_account": AgentToolDefinition(
        name="propose_create_account",
        description=(
            "Create a review-gated proposal to add a new account. "
            "Use this instead of propose_create_entity when the record is one of the user's accounts. "
            "This does not mutate accounts immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateAccountArgs,
        handler=propose_create_account,
    ),
    "propose_update_account": AgentToolDefinition(
        name="propose_update_account",
        description=(
            "Create a review-gated proposal to rename an account and/or update its currency_code, "
            "active status, or markdown_body notes. This does not mutate accounts immediately; "
            "it creates a pending review item only."
        ),
        args_model=ProposeUpdateAccountArgs,
        handler=propose_update_account,
    ),
    "propose_delete_account": AgentToolDefinition(
        name="propose_delete_account",
        description=(
            "Create a review-gated proposal to delete an account. "
            "Delete behavior preserves denormalized entry labels, clears nullable account/entity references, "
            "and deletes account snapshots. This does not mutate accounts immediately; "
            "it creates a pending review item only."
        ),
        args_model=ProposeDeleteAccountArgs,
        handler=propose_delete_account,
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
    "propose_create_group": AgentToolDefinition(
        name="propose_create_group",
        description=(
            "Create a review-gated proposal to add a new named group. "
            "Use this before proposing membership changes for a new group. "
            "This does not mutate groups immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateGroupArgs,
        handler=propose_create_group,
    ),
    "propose_update_group": AgentToolDefinition(
        name="propose_update_group",
        description=(
            "Create a review-gated proposal to rename an existing group. "
            "Prefer group_id from list_groups. This does not mutate groups immediately; "
            "it creates a pending review item only."
        ),
        args_model=ProposeUpdateGroupArgs,
        handler=propose_update_group,
    ),
    "propose_delete_group": AgentToolDefinition(
        name="propose_delete_group",
        description=(
            "Create a review-gated proposal to delete an existing group. "
            "Prefer group_id from list_groups. Delete succeeds only when the group has no direct members "
            "and is not attached as a child group. This does not mutate groups immediately; "
            "it creates a pending review item only."
        ),
        args_model=ProposeDeleteGroupArgs,
        handler=propose_delete_group,
    ),
    "propose_update_group_membership": AgentToolDefinition(
        name="propose_update_group_membership",
        description=(
            "Create a review-gated proposal to add or remove one direct group member. "
            "Use action='add' or action='remove'. Provide target.target_type='entry' with target.entry_ref "
            "or target.target_type='child_group' with target.group_ref. "
            "group_ref points to the parent group and may reference an existing group_id or, for add only, "
            "a pending create_group proposal in the current thread. target.entry_ref may reference an existing entry_id "
            "or, for add only, a pending create_entry proposal in the current thread. target.group_ref may reference "
            "an existing child group_id or, for add only, a pending create_group proposal in the current thread. "
            "member_role is required for SPLIT-group adds and rejected otherwise. "
            "This does not mutate groups immediately; it creates a pending review item only."
        ),
        args_model=ProposeUpdateGroupMembershipArgs,
        handler=propose_update_group_membership,
    ),
    "propose_update_entry": AgentToolDefinition(
        name="propose_update_entry",
        description=(
            "Create a review-gated proposal to update an existing entry. Prefer entry_id from list_entries; "
            "selector by date/amount/name/from/to is still accepted as a fallback. "
            "If entry_id or selector matches multiple entries, the tool reports ambiguity so the user can clarify. "
            "When patch.markdown_notes is provided, keep it human-readable markdown that preserves all relevant "
            "input details. For short notes, avoid headings; prefer clear line breaks and ordered/unordered lists."
        ),
        args_model=ProposeUpdateEntryArgs,
        handler=propose_update_entry,
    ),
    "propose_delete_entry": AgentToolDefinition(
        name="propose_delete_entry",
        description=(
            "Create a review-gated proposal to delete an existing entry. Prefer entry_id from list_entries; "
            "selector by date/amount/name/from/to is still accepted as a fallback. "
            "If entry_id or selector matches multiple entries, the tool reports ambiguity so the user can clarify."
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
