from __future__ import annotations

from backend.services.agent.read_tools.catalog import (
    list_accounts,
    list_entities,
    list_tags,
)
from backend.services.agent.read_tools.entries import list_entries
from backend.services.agent.read_tools.groups import list_groups
from backend.services.agent.read_tools.proposals import list_proposals
from backend.services.agent.tool_args.read import (
    ListAccountsArgs,
    ListEntitiesArgs,
    ListEntriesArgs,
    ListGroupsArgs,
    ListProposalsArgs,
    ListTagsArgs,
)
from backend.services.agent.tool_runtime_support.definitions import AgentToolDefinition


READ_TOOLS: dict[str, AgentToolDefinition] = {
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
            "List/query non-account entities by name and category. Exact matches are ranked higher than substring matches. "
            "Use this for non-account counterparties and categories; account roots are intentionally excluded. "
            "This tool is read-only."
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
}
