# CALLING SPEC:
# - Purpose: implement focused service logic for `proposal_metadata`.
# - Inputs: callers that import `backend/services/agent/proposal_metadata.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `proposal_metadata`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass

from backend.enums_agent import AgentChangeType


@dataclass(frozen=True, slots=True)
class ProposalMetadata:
    change_action: str
    proposal_type: str
    cli_command: str


_METADATA_BY_CHANGE_TYPE: dict[str, ProposalMetadata] = {
    AgentChangeType.CREATE_ENTRY.value: ProposalMetadata("create", "entry", "bh entries create"),
    AgentChangeType.UPDATE_ENTRY.value: ProposalMetadata("update", "entry", "bh entries update"),
    AgentChangeType.DELETE_ENTRY.value: ProposalMetadata("delete", "entry", "bh entries remove"),
    AgentChangeType.CREATE_GROUP.value: ProposalMetadata("create", "group", "bh groups create"),
    AgentChangeType.UPDATE_GROUP.value: ProposalMetadata("update", "group", "bh groups update"),
    AgentChangeType.DELETE_GROUP.value: ProposalMetadata("delete", "group", "bh groups remove"),
    AgentChangeType.CREATE_GROUP_MEMBER.value: ProposalMetadata(
        "create",
        "group",
        "bh groups add-member",
    ),
    AgentChangeType.DELETE_GROUP_MEMBER.value: ProposalMetadata(
        "delete",
        "group",
        "bh groups remove-member",
    ),
    AgentChangeType.CREATE_TAG.value: ProposalMetadata("create", "tag", "bh tags create"),
    AgentChangeType.UPDATE_TAG.value: ProposalMetadata("update", "tag", "bh tags update"),
    AgentChangeType.DELETE_TAG.value: ProposalMetadata("delete", "tag", "bh tags remove"),
    AgentChangeType.CREATE_ENTITY.value: ProposalMetadata("create", "entity", "bh entities create"),
    AgentChangeType.UPDATE_ENTITY.value: ProposalMetadata("update", "entity", "bh entities update"),
    AgentChangeType.DELETE_ENTITY.value: ProposalMetadata("delete", "entity", "bh entities remove"),
    AgentChangeType.CREATE_ACCOUNT.value: ProposalMetadata("create", "account", "bh accounts create"),
    AgentChangeType.UPDATE_ACCOUNT.value: ProposalMetadata("update", "account", "bh accounts update"),
    AgentChangeType.DELETE_ACCOUNT.value: ProposalMetadata("delete", "account", "bh accounts remove"),
    AgentChangeType.CREATE_SNAPSHOT.value: ProposalMetadata("create", "snapshot", "bh snapshots create"),
    AgentChangeType.DELETE_SNAPSHOT.value: ProposalMetadata("delete", "snapshot", "bh snapshots remove"),
}


def proposal_metadata_for_change_type(change_type: AgentChangeType | str) -> ProposalMetadata:
    key = change_type.value if isinstance(change_type, AgentChangeType) else str(change_type)
    return _METADATA_BY_CHANGE_TYPE.get(
        key,
        ProposalMetadata("snapshot", "other", "bh proposals get"),
    )
