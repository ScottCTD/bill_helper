# CALLING SPEC:
# - Purpose: implement focused service logic for `entry_tag_suggestion_prompt`.
# - Inputs: callers that import `backend/services/entry_tag_suggestion_prompt.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `entry_tag_suggestion_prompt`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

import json
from typing import Any

from backend.schemas_finance import EntryTagSuggestionRequest
from backend.services.entry_similarity import SimilarTaggedEntry


def _draft_payload(draft: EntryTagSuggestionRequest) -> dict[str, Any]:
    return {
        "entry_id": draft.entry_id,
        "kind": draft.kind,
        "occurred_at": draft.occurred_at.isoformat(),
        "currency_code": draft.currency_code,
        "amount_minor": draft.amount_minor,
        "name": draft.name,
        "from_entity_id": draft.from_entity_id,
        "from_entity": draft.from_entity,
        "to_entity_id": draft.to_entity_id,
        "to_entity": draft.to_entity,
        "owner_user_id": draft.owner_user_id,
        "markdown_body": draft.markdown_body,
        "current_tags": draft.current_tags,
    }


def _similar_entry_payload(example: SimilarTaggedEntry) -> dict[str, Any]:
    return {
        "entry_id": example.entry_id,
        "kind": example.kind,
        "occurred_at": example.occurred_at.isoformat(),
        "currency_code": example.currency_code,
        "amount_minor": example.amount_minor,
        "name": example.name,
        "from_entity": example.from_entity,
        "to_entity": example.to_entity,
        "markdown_body": example.markdown_body,
        "tags": example.tags,
    }


def build_entry_tag_suggestion_messages(
    *,
    draft: EntryTagSuggestionRequest,
    tag_catalog: list[dict[str, str | None]],
    similar_entries: list[SimilarTaggedEntry],
) -> list[dict[str, str]]:
    system_prompt = """
You suggest ledger entry tags.

Choose the best set of tags from the existing catalog only.
Similar entries are examples, not rules.
Current draft tags may be incomplete or wrong.
Do not overfit to the tags already present on the draft.
Do not blindly copy the tags from similar examples.
Use tag descriptions when deciding between overlapping tags.
Return no tag rather than inventing a weak match.

Your entire response must be exactly one JSON object and nothing else.
Do not use markdown fences.
Do not include any explanation, reasoning, notes, or extra text.
The first character of your response must be `{` and the last character must be `}`.
If no tag fits well, return an empty list.

Return strictly valid JSON only, with this exact shape:
{"suggested_tags":["tag_name"]}
""".strip()

    user_payload = {
        "current_entry": _draft_payload(draft),
        "tag_catalog": tag_catalog,
        "similar_tagged_entries": [_similar_entry_payload(example) for example in similar_entries],
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
    ]
