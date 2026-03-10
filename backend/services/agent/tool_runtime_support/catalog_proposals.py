from __future__ import annotations

from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload as ProposeCreateAccountArgs,
    CreateEntityPayload as ProposeCreateEntityArgs,
    CreateTagPayload as ProposeCreateTagArgs,
    DeleteAccountPayload as ProposeDeleteAccountArgs,
    DeleteEntityPayload as ProposeDeleteEntityArgs,
    DeleteTagPayload as ProposeDeleteTagArgs,
    UpdateAccountPayload as ProposeUpdateAccountArgs,
    UpdateEntityPayload as ProposeUpdateEntityArgs,
    UpdateTagPayload as ProposeUpdateTagArgs,
)
from backend.services.agent.change_contracts.entries import (
    CreateEntryPayload as ProposeCreateEntryArgs,
    DeleteEntryPayload as ProposeDeleteEntryArgs,
    UpdateEntryPayload as ProposeUpdateEntryArgs,
)
from backend.services.agent.change_contracts.groups import (
    CreateGroupPayload as ProposeCreateGroupArgs,
    DeleteGroupPayload as ProposeDeleteGroupArgs,
    UpdateGroupPayload as ProposeUpdateGroupArgs,
)
from backend.services.agent.proposals.catalog import (
    propose_create_account,
    propose_create_entity,
    propose_create_tag,
    propose_delete_account,
    propose_delete_entity,
    propose_delete_tag,
    propose_update_account,
    propose_update_entity,
    propose_update_tag,
)
from backend.services.agent.proposals.entries import (
    propose_create_entry,
    propose_delete_entry,
    propose_update_entry,
)
from backend.services.agent.proposals.group_memberships import propose_update_group_membership
from backend.services.agent.proposals.groups import (
    propose_create_group,
    propose_delete_group,
    propose_update_group,
)
from backend.services.agent.proposals.pending import (
    remove_pending_proposal,
    update_pending_proposal,
)
from backend.services.agent.tool_args.proposal_admin import (
    ProposeUpdateGroupMembershipArgs,
    RemovePendingProposalArgs,
    UpdatePendingProposalArgs,
)
from backend.services.agent.tool_runtime_support.definitions import AgentToolDefinition


PROPOSAL_TOOLS: dict[str, AgentToolDefinition] = {
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
