# CALLING SPEC:
# - Purpose: implement focused service logic for `patches`.
# - Inputs: callers that import `backend/services/agent/change_contracts/patches.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `patches`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeType
from backend.services.agent.change_contracts.common import parse_patch_path


PROPOSAL_MUTABLE_ROOTS: dict[AgentChangeType, set[str]] = {
    AgentChangeType.CREATE_TAG: {"name", "type"},
    AgentChangeType.UPDATE_TAG: {"name", "patch"},
    AgentChangeType.DELETE_TAG: {"name"},
    AgentChangeType.CREATE_ENTITY: {"name", "category"},
    AgentChangeType.UPDATE_ENTITY: {"name", "patch"},
    AgentChangeType.DELETE_ENTITY: {"name"},
    AgentChangeType.CREATE_ACCOUNT: {"name", "currency_code", "is_active", "markdown_body"},
    AgentChangeType.UPDATE_ACCOUNT: {"name", "patch"},
    AgentChangeType.DELETE_ACCOUNT: {"name"},
    AgentChangeType.CREATE_SNAPSHOT: {
        "account_id",
        "account_name",
        "currency_code",
        "snapshot_at",
        "balance_minor",
        "note",
    },
    AgentChangeType.DELETE_SNAPSHOT: {"account_id", "account_name", "currency_code", "snapshot_id"},
    AgentChangeType.CREATE_ENTRY: {
        "kind",
        "date",
        "name",
        "amount_minor",
        "currency_code",
        "from_entity",
        "to_entity",
        "tags",
        "markdown_notes",
    },
    AgentChangeType.UPDATE_ENTRY: {"entry_id", "selector", "patch"},
    AgentChangeType.DELETE_ENTRY: {"entry_id", "selector"},
    AgentChangeType.CREATE_GROUP: {"name", "group_type"},
    AgentChangeType.UPDATE_GROUP: {"group_id", "patch"},
    AgentChangeType.DELETE_GROUP: {"group_id"},
    AgentChangeType.CREATE_GROUP_MEMBER: {"action", "group_ref", "target", "member_role"},
    AgentChangeType.DELETE_GROUP_MEMBER: {"action", "group_ref", "target"},
}


def validate_patch_map_paths(change_type: AgentChangeType, patch_map: dict[str, Any]) -> None:
    allowed_roots = PROPOSAL_MUTABLE_ROOTS.get(change_type)
    if not allowed_roots:
        raise ValueError(f"unsupported proposal change type: {change_type.value}")
    disallowed = sorted(path for path in patch_map if parse_patch_path(path)[0] not in allowed_roots)
    if disallowed:
        allowed = ", ".join(sorted(allowed_roots))
        raise ValueError(
            f"patch_map includes non-editable fields for {change_type.value}: {', '.join(disallowed)}. "
            f"Allowed roots: {allowed}"
        )
