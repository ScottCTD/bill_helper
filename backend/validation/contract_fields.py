# CALLING SPEC:
# - Purpose: provide the `contract_fields` module.
# - Inputs: callers that import `backend/validation/contract_fields.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `contract_fields`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from backend.services.agent.payload_normalization import normalize_loose_text, normalize_required_text
from backend.validation.finance_names import (
    normalize_currency_code,
    normalize_currency_code_or_none,
    normalize_entity_category,
    normalize_entity_name,
    normalize_tag_name,
)


def require_loose_text(value: str) -> str:
    return normalize_required_text(value)


def optional_required_text(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_required_text(value)


def optional_loose_text(value: str | None) -> str | None:
    return normalize_loose_text(value)


def require_entity_name(value: str) -> str:
    normalized = normalize_entity_name(value)
    if not normalized:
        raise ValueError("name cannot be empty")
    return normalized


def optional_entity_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_entity_name(value)
    if not normalized:
        raise ValueError("name cannot be empty")
    return normalized


def query_entity_name(value: str | None) -> str | None:
    normalized = normalize_loose_text(value)
    return normalize_entity_name(normalized) if normalized is not None else None


def require_tag_name(value: str) -> str:
    normalized = normalize_tag_name(value)
    if not normalized:
        raise ValueError("name cannot be empty")
    return normalized


def optional_tag_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_tag_name(value)
    if not normalized:
        raise ValueError("name cannot be empty")
    return normalized


def query_tag_name(value: str | None) -> str | None:
    normalized = normalize_loose_text(value)
    return normalize_tag_name(normalized) if normalized is not None else None


def require_category(value: str) -> str:
    normalized = normalize_entity_category(value)
    if normalized is None:
        raise ValueError("category cannot be empty")
    return normalized


def optional_category(value: str | None) -> str | None:
    return normalize_entity_category(value)


def require_currency_code(value: str) -> str:
    normalized = normalize_currency_code(value)
    if not normalized:
        raise ValueError("currency_code cannot be empty")
    return normalized


def optional_currency_code(value: str | None) -> str | None:
    normalized = normalize_currency_code_or_none(value)
    if value is not None and normalized is None:
        raise ValueError("currency_code cannot be empty")
    return normalized


def normalize_tag_list(value: list[str]) -> list[str]:
    return sorted({normalize_tag_name(tag) for tag in value if tag.strip()})


class NonEmptyPatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> NonEmptyPatchModel:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


RequiredLooseText = Annotated[str, AfterValidator(require_loose_text)]
OptionalRequiredText = Annotated[str | None, AfterValidator(optional_required_text)]
OptionalLooseText = Annotated[str | None, AfterValidator(optional_loose_text)]
RequiredEntityName = Annotated[str, AfterValidator(require_entity_name)]
OptionalEntityName = Annotated[str | None, AfterValidator(optional_entity_name)]
QueryEntityName = Annotated[str | None, AfterValidator(query_entity_name)]
RequiredTagName = Annotated[str, AfterValidator(require_tag_name)]
OptionalTagName = Annotated[str | None, AfterValidator(optional_tag_name)]
QueryTagName = Annotated[str | None, AfterValidator(query_tag_name)]
RequiredCategory = Annotated[str, AfterValidator(require_category)]
OptionalCategory = Annotated[str | None, AfterValidator(optional_category)]
RequiredCurrencyCode = Annotated[str, AfterValidator(require_currency_code)]
OptionalCurrencyCode = Annotated[str | None, AfterValidator(optional_currency_code)]
NormalizedTagList = Annotated[list[str], AfterValidator(normalize_tag_list)]
