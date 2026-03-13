# CALLING SPEC:
# - Purpose: implement focused service logic for `payload_normalization`.
# - Inputs: callers that import `backend/services/agent/payload_normalization.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `payload_normalization`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from backend.validation.finance_names import normalize_entity_category


def normalize_loose_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def normalize_required_text(value: str) -> str:
    normalized = normalize_loose_text(value)
    if normalized is None:
        raise ValueError("value cannot be empty")
    return normalized


def normalize_optional_category(value: str | None) -> str | None:
    return normalize_entity_category(value)
