from __future__ import annotations

from typing import Any

from backend.services.agent.payload_normalization import normalize_loose_text, normalize_required_text


def normalize_object_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    candidate = value.strip()
    if not candidate or not (candidate.startswith("{") and candidate.endswith("}")):
        return value
    try:
        import json

        decoded = json.loads(candidate)
    except (TypeError, ValueError):
        return value
    return decoded if isinstance(decoded, dict) else value


def normalize_optional_reference_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_loose_text(value)
    return normalized.lower() if normalized is not None else None


def normalize_optional_proposal_id(value: str | None) -> str | None:
    return normalize_optional_reference_id(value)


def parse_patch_path(path: str) -> list[str]:
    normalized = normalize_required_text(path)
    parts = [part.strip() for part in normalized.split(".")]
    if any(not part for part in parts):
        raise ValueError("patch_map path segments cannot be empty")
    return parts
