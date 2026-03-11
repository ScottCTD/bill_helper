from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeType
from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload,
    CreateEntityPayload,
    SnapshotCreatePayload,
    SnapshotDeletePayload,
    CreateTagPayload,
    DeleteAccountPayload,
    DeleteEntityPayload,
    DeleteTagPayload,
    UpdateAccountPayload,
    UpdateEntityPayload,
    UpdateTagPayload,
)
from backend.services.agent.proposals.normalization_common import parse_typed_change_payload
from backend.services.agent.tool_types import ToolContext
from backend.services.entities import ACCOUNT_CATEGORY_DETAIL
from backend.validation.finance_names import normalize_entity_category


def normalize_create_tag_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.CREATE_TAG,
        payload=payload,
        model_type=CreateTagPayload,
    )
    return parsed.model_dump(mode="json")


def normalize_update_tag_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.UPDATE_TAG,
        payload={"name": payload.get("name"), "patch": payload.get("patch")},
        model_type=UpdateTagPayload,
    )
    normalized_payload: dict[str, Any] = {
        "name": parsed.name,
        "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
    }
    if isinstance(payload.get("current"), dict):
        normalized_payload["current"] = payload["current"]
    return normalized_payload


def normalize_delete_tag_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.DELETE_TAG,
        payload=payload,
        model_type=DeleteTagPayload,
    )
    return parsed.model_dump(mode="json")


def normalize_create_entity_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.CREATE_ENTITY,
        payload=payload,
        model_type=CreateEntityPayload,
    )
    if normalize_entity_category(parsed.category) == "account":
        raise ValueError(ACCOUNT_CATEGORY_DETAIL)
    return parsed.model_dump(mode="json")


def normalize_update_entity_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.UPDATE_ENTITY,
        payload={"name": payload.get("name"), "patch": payload.get("patch")},
        model_type=UpdateEntityPayload,
    )
    if normalize_entity_category(parsed.patch.category) == "account":
        raise ValueError(ACCOUNT_CATEGORY_DETAIL)
    normalized_payload = {
        "name": parsed.name,
        "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
    }
    if isinstance(payload.get("current"), dict):
        normalized_payload["current"] = payload["current"]
    return normalized_payload


def normalize_delete_entity_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.DELETE_ENTITY,
        payload=payload,
        model_type=DeleteEntityPayload,
    )
    normalized_payload = parsed.model_dump(mode="json")
    if isinstance(payload.get("impact_preview"), dict):
        normalized_payload["impact_preview"] = payload["impact_preview"]
    return normalized_payload


def normalize_create_account_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.CREATE_ACCOUNT,
        payload=payload,
        model_type=CreateAccountPayload,
    )
    return parsed.model_dump(mode="json")


def normalize_update_account_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.UPDATE_ACCOUNT,
        payload={"name": payload.get("name"), "patch": payload.get("patch")},
        model_type=UpdateAccountPayload,
    )
    normalized_payload = {
        "name": parsed.name,
        "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
    }
    if isinstance(payload.get("current"), dict):
        normalized_payload["current"] = payload["current"]
    return normalized_payload


def normalize_delete_account_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.DELETE_ACCOUNT,
        payload=payload,
        model_type=DeleteAccountPayload,
    )
    normalized_payload = parsed.model_dump(mode="json")
    if isinstance(payload.get("impact_preview"), dict):
        normalized_payload["impact_preview"] = payload["impact_preview"]
    return normalized_payload


def normalize_create_snapshot_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.CREATE_SNAPSHOT,
        payload=payload,
        model_type=SnapshotCreatePayload,
    )
    return parsed.model_dump(mode="json")


def normalize_delete_snapshot_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.DELETE_SNAPSHOT,
        payload=payload,
        model_type=SnapshotDeletePayload,
    )
    normalized_payload = parsed.model_dump(mode="json")
    if isinstance(payload.get("impact_preview"), dict):
        normalized_payload["impact_preview"] = payload["impact_preview"]
    return normalized_payload


CATALOG_PAYLOAD_NORMALIZERS = {
    AgentChangeType.CREATE_TAG: normalize_create_tag_payload,
    AgentChangeType.UPDATE_TAG: normalize_update_tag_payload,
    AgentChangeType.DELETE_TAG: normalize_delete_tag_payload,
    AgentChangeType.CREATE_ENTITY: normalize_create_entity_payload,
    AgentChangeType.UPDATE_ENTITY: normalize_update_entity_payload,
    AgentChangeType.DELETE_ENTITY: normalize_delete_entity_payload,
    AgentChangeType.CREATE_ACCOUNT: normalize_create_account_payload,
    AgentChangeType.UPDATE_ACCOUNT: normalize_update_account_payload,
    AgentChangeType.DELETE_ACCOUNT: normalize_delete_account_payload,
    AgentChangeType.CREATE_SNAPSHOT: normalize_create_snapshot_payload,
    AgentChangeType.DELETE_SNAPSHOT: normalize_delete_snapshot_payload,
}
