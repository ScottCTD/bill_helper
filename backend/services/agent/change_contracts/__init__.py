from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from pydantic import BaseModel

from backend.enums_agent import AgentChangeType
from . import catalog as catalog_contracts
from . import entries as entry_contracts
from . import groups as group_contracts
from .patches import (
    PROPOSAL_MUTABLE_ROOTS,
    parse_patch_path,
    validate_patch_map_paths,
)


CHANGE_PAYLOAD_MODELS: dict[AgentChangeType, type[BaseModel]] = {
    AgentChangeType.CREATE_TAG: catalog_contracts.CreateTagPayload,
    AgentChangeType.UPDATE_TAG: catalog_contracts.UpdateTagPayload,
    AgentChangeType.DELETE_TAG: catalog_contracts.DeleteTagPayload,
    AgentChangeType.CREATE_ENTITY: catalog_contracts.CreateEntityPayload,
    AgentChangeType.UPDATE_ENTITY: catalog_contracts.UpdateEntityPayload,
    AgentChangeType.DELETE_ENTITY: catalog_contracts.DeleteEntityPayload,
    AgentChangeType.CREATE_ACCOUNT: catalog_contracts.CreateAccountPayload,
    AgentChangeType.UPDATE_ACCOUNT: catalog_contracts.UpdateAccountPayload,
    AgentChangeType.DELETE_ACCOUNT: catalog_contracts.DeleteAccountPayload,
    AgentChangeType.CREATE_SNAPSHOT: catalog_contracts.SnapshotCreatePayload,
    AgentChangeType.DELETE_SNAPSHOT: catalog_contracts.SnapshotDeletePayload,
    AgentChangeType.CREATE_ENTRY: entry_contracts.CreateEntryPayload,
    AgentChangeType.UPDATE_ENTRY: entry_contracts.UpdateEntryPayload,
    AgentChangeType.DELETE_ENTRY: entry_contracts.DeleteEntryPayload,
    AgentChangeType.CREATE_GROUP: group_contracts.CreateGroupPayload,
    AgentChangeType.UPDATE_GROUP: group_contracts.UpdateGroupPayload,
    AgentChangeType.DELETE_GROUP: group_contracts.DeleteGroupPayload,
    AgentChangeType.CREATE_GROUP_MEMBER: group_contracts.CreateGroupMemberPayload,
    AgentChangeType.DELETE_GROUP_MEMBER: group_contracts.DeleteGroupMemberPayload,
}
CHANGE_PAYLOAD_MODEL_TYPES = tuple(CHANGE_PAYLOAD_MODELS.values())


type ChangePayloadModel = (
    catalog_contracts.CreateTagPayload
    | catalog_contracts.UpdateTagPayload
    | catalog_contracts.DeleteTagPayload
    | catalog_contracts.CreateEntityPayload
    | catalog_contracts.UpdateEntityPayload
    | catalog_contracts.DeleteEntityPayload
    | catalog_contracts.CreateAccountPayload
    | catalog_contracts.UpdateAccountPayload
    | catalog_contracts.DeleteAccountPayload
    | catalog_contracts.SnapshotCreatePayload
    | catalog_contracts.SnapshotDeletePayload
    | entry_contracts.CreateEntryPayload
    | entry_contracts.UpdateEntryPayload
    | entry_contracts.DeleteEntryPayload
    | group_contracts.CreateGroupPayload
    | group_contracts.UpdateGroupPayload
    | group_contracts.DeleteGroupPayload
    | group_contracts.CreateGroupMemberPayload
    | group_contracts.DeleteGroupMemberPayload
)


def validate_change_payload(change_type: AgentChangeType, payload: dict[str, Any]) -> BaseModel:
    model_type = CHANGE_PAYLOAD_MODELS.get(change_type)
    if model_type is None:  # pragma: no cover - enum guard
        raise ValueError(f"unsupported proposal change type: {change_type.value}")
    return model_type.model_validate(payload)


def parse_change_payload(
    change_type: AgentChangeType,
    payload: Mapping[str, Any],
) -> ChangePayloadModel:
    parsed = validate_change_payload(change_type, dict(payload))
    if not isinstance(parsed, CHANGE_PAYLOAD_MODEL_TYPES):  # pragma: no cover - enum/model map guard
        raise ValueError(f"unsupported proposal change type: {change_type.value}")
    return cast(ChangePayloadModel, parsed)


__all__ = [
    "CHANGE_PAYLOAD_MODELS",
    "PROPOSAL_MUTABLE_ROOTS",
    "ChangePayloadModel",
    "parse_change_payload",
    "parse_patch_path",
    "validate_change_payload",
    "validate_patch_map_paths",
]
