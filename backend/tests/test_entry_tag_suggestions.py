from __future__ import annotations

import json

from backend.auth.contracts import RequestPrincipal
from backend.database import get_session_maker
from backend.schemas_finance import EntryTagSuggestionRequest
from backend.services.entry_similarity import list_similar_tagged_entries


def create_account(client, name: str = "Checking") -> str:
    response = client.post(
        "/api/v1/accounts",
        json={
            "name": name,
            "currency_code": "USD",
            "is_active": True,
        },
    )
    response.raise_for_status()
    return response.json()["id"]


def create_tag(client, name: str, *, description: str | None = None) -> None:
    response = client.post(
        "/api/v1/tags",
        json={
            "name": name,
            "description": description,
        },
    )
    response.raise_for_status()


def create_tagged_entry(
    client,
    *,
    account_id: str,
    name: str,
    tags: list[str],
    kind: str = "EXPENSE",
    occurred_at: str = "2026-03-01",
    amount_minor: int = 1500,
    currency_code: str = "USD",
    from_entity: str | None = None,
    to_entity: str | None = None,
    markdown_body: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": kind,
            "occurred_at": occurred_at,
            "name": name,
            "amount_minor": amount_minor,
            "currency_code": currency_code,
            "from_entity": from_entity,
            "to_entity": to_entity,
            "markdown_body": markdown_body,
            "tags": tags,
        },
    )
    response.raise_for_status()
    return response.json()


def enable_entry_tagging_model(client, model_name: str = "openai/gpt-4.1-mini") -> None:
    response = client.patch(
        "/api/v1/settings",
        json={
            "available_agent_models": [model_name],
            "entry_tagging_model": model_name,
        },
    )
    response.raise_for_status()


def draft_payload(**overrides) -> dict:
    payload = {
        "kind": "EXPENSE",
        "occurred_at": "2026-03-10",
        "currency_code": "USD",
        "amount_minor": 1599,
        "name": "Coffee Beans",
        "from_entity": "Checking",
        "to_entity": "Neighborhood Cafe",
        "markdown_body": "Morning coffee restock",
        "current_tags": [],
    }
    payload.update(overrides)
    return payload


def test_post_entry_tag_suggestion_returns_existing_catalog_tags(client, monkeypatch) -> None:
    account_id = create_account(client)
    create_tag(client, "grocery", description="Groceries and pantry restocks.")
    create_tag(client, "day_to_day", description="Everyday recurring spending.")
    create_tagged_entry(
        client,
        account_id=account_id,
        name="Coffee Beans",
        tags=["grocery", "day_to_day"],
        amount_minor=1499,
        from_entity="Checking",
        to_entity="Neighborhood Cafe",
        markdown_body="Coffee beans and pantry refill",
    )
    enable_entry_tagging_model(client)

    captured_model_call: dict[str, object] = {}

    monkeypatch.setattr("backend.services.entry_tag_suggestions.ensure_agent_available", lambda *_args, **_kwargs: None)

    def fake_call_model(messages, *_args, **kwargs):
        captured_model_call["messages"] = messages
        captured_model_call["kwargs"] = kwargs
        return {"content": json.dumps({"suggested_tags": ["grocery", "day_to_day"]})}

    monkeypatch.setattr("backend.services.entry_tag_suggestions.call_model", fake_call_model)

    response = client.post("/api/v1/entries/tag-suggestion", json=draft_payload())
    response.raise_for_status()

    assert response.json() == {"suggested_tags": ["grocery", "day_to_day"]}
    messages = captured_model_call["messages"]
    assert isinstance(messages, list)
    user_payload = json.loads(messages[1]["content"])
    assert user_payload["tag_catalog"][0]["description"] is not None
    assert len(user_payload["similar_tagged_entries"]) == 1
    assert captured_model_call["kwargs"] == {
        "model_name": "openai/gpt-4.1-mini",
        "response_format": {
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
                                "enum": ["day_to_day", "grocery"],
                            },
                        }
                    },
                    "required": ["suggested_tags"],
                },
            },
        },
        "tools": [],
    }


def test_post_entry_tag_suggestion_rejects_blank_tagging_model(client) -> None:
    response = client.post("/api/v1/entries/tag-suggestion", json=draft_payload())

    assert response.status_code == 400
    assert response.json()["detail"] == "AI tag suggestion is disabled until you set Default tagging model in Settings."


def test_post_entry_tag_suggestion_rejects_malformed_json(client, monkeypatch) -> None:
    enable_entry_tagging_model(client)
    monkeypatch.setattr("backend.services.entry_tag_suggestions.ensure_agent_available", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("backend.services.entry_tag_suggestions.call_model", lambda *_args, **_kwargs: {"content": "not-json"})

    response = client.post("/api/v1/entries/tag-suggestion", json=draft_payload())

    assert response.status_code == 400
    assert response.json()["detail"] == "AI tag suggestion returned malformed JSON."


def test_post_entry_tag_suggestion_rejects_unknown_tags(client, monkeypatch) -> None:
    enable_entry_tagging_model(client)
    create_tag(client, "grocery")
    monkeypatch.setattr("backend.services.entry_tag_suggestions.ensure_agent_available", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "backend.services.entry_tag_suggestions.call_model",
        lambda *_args, **_kwargs: {"content": json.dumps({"suggested_tags": ["unknown_tag"]})},
    )

    response = client.post("/api/v1/entries/tag-suggestion", json=draft_payload())

    assert response.status_code == 400
    assert response.json()["detail"] == "AI tag suggestion returned a tag outside the existing catalog."


def test_post_entry_tag_suggestion_excludes_current_entry_from_similarity_examples(client, monkeypatch) -> None:
    account_id = create_account(client)
    create_tag(client, "coffee")
    current_entry = create_tagged_entry(
        client,
        account_id=account_id,
        name="Coffee Beans",
        tags=["coffee"],
        from_entity="Checking",
        to_entity="Neighborhood Cafe",
    )
    other_entry = create_tagged_entry(
        client,
        account_id=account_id,
        name="Coffee Beans Restock",
        tags=["coffee"],
        from_entity="Checking",
        to_entity="Neighborhood Cafe",
    )
    enable_entry_tagging_model(client)

    captured_messages: dict[str, object] = {}
    monkeypatch.setattr("backend.services.entry_tag_suggestions.ensure_agent_available", lambda *_args, **_kwargs: None)

    def fake_call_model(messages, *_args, **_kwargs):
        captured_messages["messages"] = messages
        return {"content": json.dumps({"suggested_tags": ["coffee"]})}

    monkeypatch.setattr("backend.services.entry_tag_suggestions.call_model", fake_call_model)

    response = client.post(
        "/api/v1/entries/tag-suggestion",
        json=draft_payload(entry_id=current_entry["id"]),
    )
    response.raise_for_status()

    messages = captured_messages["messages"]
    assert isinstance(messages, list)
    user_payload = json.loads(messages[1]["content"])
    assert [item["entry_id"] for item in user_payload["similar_tagged_entries"]] == [other_entry["id"]]


def test_post_entry_tag_suggestion_runs_without_examples_when_similarity_is_empty(client, monkeypatch) -> None:
    create_tag(client, "grocery")
    enable_entry_tagging_model(client)

    captured_messages: dict[str, object] = {}
    monkeypatch.setattr("backend.services.entry_tag_suggestions.ensure_agent_available", lambda *_args, **_kwargs: None)

    def fake_call_model(messages, *_args, **_kwargs):
        captured_messages["messages"] = messages
        return {"content": json.dumps({"suggested_tags": []})}

    monkeypatch.setattr("backend.services.entry_tag_suggestions.call_model", fake_call_model)

    response = client.post("/api/v1/entries/tag-suggestion", json=draft_payload())
    response.raise_for_status()

    messages = captured_messages["messages"]
    assert isinstance(messages, list)
    user_payload = json.loads(messages[1]["content"])
    assert user_payload["similar_tagged_entries"] == []


def test_list_similar_tagged_entries_prefers_same_kind_and_excludes_current_entry(client) -> None:
    account_id = create_account(client)
    current_entry = create_tagged_entry(
        client,
        account_id=account_id,
        name="Coffee Beans",
        tags=["coffee"],
        kind="EXPENSE",
        from_entity="Checking",
        to_entity="Neighborhood Cafe",
    )
    strong_same_kind = create_tagged_entry(
        client,
        account_id=account_id,
        name="Coffee Beans",
        tags=["coffee"],
        kind="EXPENSE",
        occurred_at="2026-03-09",
        from_entity="Checking",
        to_entity="Neighborhood Cafe",
    )
    weaker_same_kind = create_tagged_entry(
        client,
        account_id=account_id,
        name="Coffee Supplies",
        tags=["coffee"],
        kind="EXPENSE",
        occurred_at="2026-03-08",
        from_entity="Checking",
        to_entity="Cafe Market",
    )
    cross_kind = create_tagged_entry(
        client,
        account_id=account_id,
        name="Coffee Beans",
        tags=["coffee"],
        kind="INCOME",
        occurred_at="2026-03-07",
        from_entity="Coffee Vendor",
        to_entity="Checking",
    )

    make_session = get_session_maker()
    db = make_session()
    try:
        similar_entries = list_similar_tagged_entries(
            db,
            principal=RequestPrincipal(user_id="admin-user", user_name="admin", is_admin=True),
            draft=EntryTagSuggestionRequest.model_validate(draft_payload(entry_id=current_entry["id"])),
        )
    finally:
        db.close()

    assert [entry.entry_id for entry in similar_entries] == [
        strong_same_kind["id"],
        weaker_same_kind["id"],
        cross_kind["id"],
    ]
