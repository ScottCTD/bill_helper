from __future__ import annotations

from dataclasses import dataclass

from backend.enums_agent import AgentChangeType


@dataclass(frozen=True, slots=True)
class ProposalMetadata:
    change_action: str
    proposal_type: str
    proposal_tool_name: str


_METADATA_BY_CHANGE_TYPE: dict[str, ProposalMetadata] = {
    AgentChangeType.CREATE_ENTRY.value: ProposalMetadata("create", "entry", "propose_create_entry"),
    AgentChangeType.UPDATE_ENTRY.value: ProposalMetadata("update", "entry", "propose_update_entry"),
    AgentChangeType.DELETE_ENTRY.value: ProposalMetadata("delete", "entry", "propose_delete_entry"),
    AgentChangeType.CREATE_GROUP.value: ProposalMetadata("create", "group", "propose_create_group"),
    AgentChangeType.UPDATE_GROUP.value: ProposalMetadata("update", "group", "propose_update_group"),
    AgentChangeType.DELETE_GROUP.value: ProposalMetadata("delete", "group", "propose_delete_group"),
    AgentChangeType.CREATE_GROUP_MEMBER.value: ProposalMetadata(
        "create",
        "group",
        "propose_update_group_membership",
    ),
    AgentChangeType.DELETE_GROUP_MEMBER.value: ProposalMetadata(
        "delete",
        "group",
        "propose_update_group_membership",
    ),
    AgentChangeType.CREATE_TAG.value: ProposalMetadata("create", "tag", "propose_create_tag"),
    AgentChangeType.UPDATE_TAG.value: ProposalMetadata("update", "tag", "propose_update_tag"),
    AgentChangeType.DELETE_TAG.value: ProposalMetadata("delete", "tag", "propose_delete_tag"),
    AgentChangeType.CREATE_ENTITY.value: ProposalMetadata("create", "entity", "propose_create_entity"),
    AgentChangeType.UPDATE_ENTITY.value: ProposalMetadata("update", "entity", "propose_update_entity"),
    AgentChangeType.DELETE_ENTITY.value: ProposalMetadata("delete", "entity", "propose_delete_entity"),
    AgentChangeType.CREATE_ACCOUNT.value: ProposalMetadata("create", "account", "propose_create_account"),
    AgentChangeType.UPDATE_ACCOUNT.value: ProposalMetadata("update", "account", "propose_update_account"),
    AgentChangeType.DELETE_ACCOUNT.value: ProposalMetadata("delete", "account", "propose_delete_account"),
    AgentChangeType.CREATE_SNAPSHOT.value: ProposalMetadata("create", "snapshot", "propose_create_snapshot"),
    AgentChangeType.DELETE_SNAPSHOT.value: ProposalMetadata("delete", "snapshot", "propose_delete_snapshot"),
}


def proposal_metadata_for_change_type(change_type: AgentChangeType | str) -> ProposalMetadata:
    key = change_type.value if isinstance(change_type, AgentChangeType) else str(change_type)
    return _METADATA_BY_CHANGE_TYPE.get(
        key,
        ProposalMetadata("snapshot", "other", "proposal_tool_result"),
    )
