# CALLING SPEC:
# - Purpose: implement focused service logic for `dispatch`.
# - Inputs: callers that import `backend/services/agent/apply/dispatch.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `dispatch`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.enums_agent import AgentChangeType
from backend.services.agent.apply.catalog import (
    apply_create_account,
    apply_create_entity,
    apply_create_snapshot,
    apply_create_tag,
    apply_delete_account,
    apply_delete_entity,
    apply_delete_snapshot,
    apply_delete_tag,
    apply_update_account,
    apply_update_entity,
    apply_update_tag,
)
from backend.services.agent.apply.common import AppliedResource, ChangeApplyHandler
from backend.services.agent.apply.entries import (
    apply_create_entry,
    apply_delete_entry,
    apply_update_entry,
)
from backend.services.agent.apply.groups import (
    apply_create_group,
    apply_create_group_member,
    apply_delete_group,
    apply_delete_group_member,
    apply_update_group,
)
from backend.services.agent.change_contracts import ChangePayloadModel


APPLY_CHANGE_HANDLERS: dict[AgentChangeType, ChangeApplyHandler] = {
    AgentChangeType.CREATE_ENTRY: apply_create_entry,
    AgentChangeType.UPDATE_ENTRY: apply_update_entry,
    AgentChangeType.DELETE_ENTRY: apply_delete_entry,
    AgentChangeType.CREATE_ACCOUNT: apply_create_account,
    AgentChangeType.UPDATE_ACCOUNT: apply_update_account,
    AgentChangeType.DELETE_ACCOUNT: apply_delete_account,
    AgentChangeType.CREATE_SNAPSHOT: apply_create_snapshot,
    AgentChangeType.DELETE_SNAPSHOT: apply_delete_snapshot,
    AgentChangeType.CREATE_GROUP: apply_create_group,
    AgentChangeType.UPDATE_GROUP: apply_update_group,
    AgentChangeType.DELETE_GROUP: apply_delete_group,
    AgentChangeType.CREATE_GROUP_MEMBER: apply_create_group_member,
    AgentChangeType.DELETE_GROUP_MEMBER: apply_delete_group_member,
    AgentChangeType.CREATE_TAG: apply_create_tag,
    AgentChangeType.UPDATE_TAG: apply_update_tag,
    AgentChangeType.DELETE_TAG: apply_delete_tag,
    AgentChangeType.CREATE_ENTITY: apply_create_entity,
    AgentChangeType.UPDATE_ENTITY: apply_update_entity,
    AgentChangeType.DELETE_ENTITY: apply_delete_entity,
}


def apply_change_item_payload(
    db: Session,
    *,
    change_type: AgentChangeType,
    payload: ChangePayloadModel,
    principal: RequestPrincipal,
) -> AppliedResource:
    handler = APPLY_CHANGE_HANDLERS.get(change_type)
    if handler is None:  # pragma: no cover - enum guard
        raise ValueError(f"Unsupported change type: {change_type}")
    return handler(db, payload, principal)
