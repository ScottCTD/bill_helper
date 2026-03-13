# CALLING SPEC:
# - Purpose: implement focused service logic for `entry_tag_suggestions`.
# - Inputs: callers that import `backend/services/entry_tag_suggestions.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `entry_tag_suggestions`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from backend.auth.contracts import RequestPrincipal
from backend.models_finance import Tag
from backend.schemas_finance import EntryTagSuggestionRequest
from backend.services.agent.model_client import AgentModelError
from backend.services.agent.runtime import AgentRuntimeUnavailable, call_model, ensure_agent_available
from backend.services.entry_similarity import list_similar_tagged_entries
from backend.services.entry_tag_suggestion_prompt import build_entry_tag_suggestion_messages
from backend.services.runtime_settings import resolve_runtime_settings
from backend.validation.finance_names import normalize_tag_name


@dataclass(slots=True)
class EntryTagSuggestionError(Exception):
    detail: str
    status_code: int


class _ModelTagSuggestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggested_tags: list[str] = Field(default_factory=list)


def _normalized_catalog(db: Session) -> tuple[list[dict[str, str | None]], dict[str, str]]:
    tags = list(db.scalars(select(Tag).order_by(Tag.name.asc())))
    catalog_payload = [
        {
            "name": tag.name,
            "description": tag.description,
        }
        for tag in tags
    ]
    tag_name_by_normalized_name = {normalize_tag_name(tag.name): tag.name for tag in tags}
    return catalog_payload, tag_name_by_normalized_name


def _response_format_for_catalog(tag_catalog: list[dict[str, str | None]]) -> dict[str, object]:
    allowed_tag_names = [tag["name"] for tag in tag_catalog if isinstance(tag.get("name"), str)]
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "entry_tag_suggestion",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "suggested_tags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": allowed_tag_names,
                        },
                    }
                },
                "required": ["suggested_tags"],
            },
        },
    }


def _normalize_weak_context_tags(raw_tags: list[str]) -> list[str]:
    normalized_tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw_tags:
        normalized_tag = normalize_tag_name(raw_tag)
        if not normalized_tag or normalized_tag in seen:
            continue
        seen.add(normalized_tag)
        normalized_tags.append(normalized_tag)
    return normalized_tags


def _parse_model_suggested_tags(content: str, *, tag_name_by_normalized_name: dict[str, str]) -> list[str]:
    try:
        decoded = json.loads(content)
        payload = _ModelTagSuggestionPayload.model_validate(decoded)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise EntryTagSuggestionError(
            detail="AI tag suggestion returned malformed JSON.",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc

    normalized_suggested_tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in payload.suggested_tags:
        normalized_tag = normalize_tag_name(raw_tag)
        if not normalized_tag or normalized_tag in seen:
            continue
        canonical_tag = tag_name_by_normalized_name.get(normalized_tag)
        if canonical_tag is None:
            raise EntryTagSuggestionError(
                detail="AI tag suggestion returned a tag outside the existing catalog.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        seen.add(normalized_tag)
        normalized_suggested_tags.append(canonical_tag)

    return normalized_suggested_tags


def suggest_entry_tags(
    db: Session,
    *,
    principal: RequestPrincipal,
    draft: EntryTagSuggestionRequest,
) -> list[str]:
    normalized_current_tags = _normalize_weak_context_tags(draft.current_tags)
    request_draft = draft.model_copy(update={"current_tags": normalized_current_tags})

    try:
        settings = resolve_runtime_settings(db)
    except ValueError as exc:
        raise EntryTagSuggestionError(
            detail=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc

    if not settings.entry_tagging_model:
        raise EntryTagSuggestionError(
            detail="AI tag suggestion is disabled until you set Default tagging model in Settings.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    tag_catalog, tag_name_by_normalized_name = _normalized_catalog(db)
    response_format = _response_format_for_catalog(tag_catalog)
    similar_entries = list_similar_tagged_entries(
        db,
        principal=principal,
        draft=request_draft,
    )
    messages = build_entry_tag_suggestion_messages(
        draft=request_draft,
        tag_catalog=tag_catalog,
        similar_entries=similar_entries,
    )

    try:
        ensure_agent_available(db, model_name=settings.entry_tagging_model)
        response = call_model(
            messages,
            db,
            model_name=settings.entry_tagging_model,
            tools=[],
            response_format=response_format,
        )
    except AgentRuntimeUnavailable as exc:
        raise EntryTagSuggestionError(
            detail=str(exc),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    except AgentModelError as exc:
        raise EntryTagSuggestionError(
            detail=str(exc),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    return _parse_model_suggested_tags(
        response.get("content", ""),
        tag_name_by_normalized_name=tag_name_by_normalized_name,
    )
