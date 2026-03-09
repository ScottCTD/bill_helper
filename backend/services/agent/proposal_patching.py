from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.services.agent.change_contracts.patches import parse_patch_path


def _set_nested_value(target: dict[str, Any], path_parts: list[str], value: Any) -> None:
    node: dict[str, Any] = target
    for part in path_parts[:-1]:
        child = node.get(part)
        if child is None:
            child = {}
            node[part] = child
        if not isinstance(child, dict):
            raise ValueError(f"patch_map path '{'.'.join(path_parts)}' crosses non-object field '{part}'")
        node = child
    node[path_parts[-1]] = value


def apply_patch_map_to_payload(payload: dict[str, Any], patch_map: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(payload)
    for path, value in patch_map.items():
        parts = parse_patch_path(path)
        _set_nested_value(updated, parts, value)
    return updated
