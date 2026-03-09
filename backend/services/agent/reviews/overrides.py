from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.enums_agent import AgentChangeType
from backend.models_agent import AgentChangeItem
from backend.services.agent.change_contracts import ChangePayloadModel, parse_change_payload
from backend.services.agent.proposals.normalization import normalize_payload_for_change_type
from backend.services.agent.tool_types import ToolContext


EDITABLE_CHANGE_TYPES = {
    AgentChangeType.CREATE_TAG,
    AgentChangeType.UPDATE_TAG,
    AgentChangeType.CREATE_ENTITY,
    AgentChangeType.UPDATE_ENTITY,
    AgentChangeType.CREATE_ACCOUNT,
    AgentChangeType.UPDATE_ACCOUNT,
    AgentChangeType.CREATE_ENTRY,
    AgentChangeType.UPDATE_ENTRY,
    AgentChangeType.CREATE_GROUP,
    AgentChangeType.UPDATE_GROUP,
    AgentChangeType.CREATE_GROUP_MEMBER,
}


def summarize_payload_override_diff(base_payload: dict[str, Any], override_payload: dict[str, Any]) -> str:
    def _is_record(value: Any) -> bool:
        return isinstance(value, dict)

    def _format_value(value: Any) -> str:
        if isinstance(value, str):
            return repr(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return repr(value)
        if isinstance(value, list):
            preview = ", ".join(_format_value(item) for item in value[:4])
            if len(value) > 4:
                preview = f"{preview}, ... (+{len(value) - 4} more)"
            return f"[{preview}]"
        if isinstance(value, dict):
            return "{...}"
        return repr(value)

    def _walk_differences(
        base_value: Any,
        override_value: Any,
        *,
        path: str,
        output: list[str],
    ) -> None:
        if base_value == override_value:
            return

        if _is_record(base_value) and _is_record(override_value):
            keys = sorted(set(base_value) | set(override_value))
            for key in keys:
                next_path = f"{path}.{key}" if path else key
                _walk_differences(base_value.get(key), override_value.get(key), path=next_path, output=output)
            return

        output.append(f"{path}={_format_value(override_value)}")

    changed_values: list[str] = []
    _walk_differences(base_payload, override_payload, path="", output=changed_values)
    if not changed_values:
        return ""
    if len(changed_values) <= 8:
        return "; ".join(changed_values)
    return f"{'; '.join(changed_values[:8])}; ... (+{len(changed_values) - 8} more)"


def validate_payload_override_supported(item: AgentChangeItem, payload_override: dict[str, Any] | None) -> None:
    if payload_override is None:
        return
    if item.change_type not in EDITABLE_CHANGE_TYPES:
        raise ValueError(
            "payload_override is only supported for editable create/update entry, tag, entity, account, and group items"
        )


def normalized_payload_override(
    db: Session,
    *,
    item: AgentChangeItem,
    payload_override: dict[str, Any] | None,
) -> tuple[dict[str, Any], ChangePayloadModel]:
    validate_payload_override_supported(item, payload_override)
    if payload_override is None:
        payload_json = item.payload_json
    else:
        payload_json = normalize_payload_for_change_type(
            ToolContext(db=db, run_id=item.run_id),
            change_type=item.change_type,
            payload=payload_override,
        )
    return payload_json, parse_change_payload(item.change_type, payload_json)
