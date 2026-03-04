from __future__ import annotations

import json
import time
from inspect import signature


def patch_model(monkeypatch, handler):
    from backend.services.agent import runtime

    handler_params = signature(handler).parameters
    params = list(handler_params.values())
    accepts_db = len(params) > 1 and params[1].kind in (
        params[1].POSITIONAL_ONLY,
        params[1].POSITIONAL_OR_KEYWORD,
        params[1].VAR_POSITIONAL,
    )
    accepts_kwargs = any(param.kind == param.VAR_KEYWORD for param in handler_params.values())
    accepts_observability = "observability" in handler_params

    def wrapped(messages, db, **kwargs):
        if accepts_db:
            if accepts_kwargs or accepts_observability:
                return handler(messages, db, **kwargs)
            return handler(messages, db)
        if accepts_kwargs or accepts_observability:
            return handler(messages, **kwargs)
        return handler(messages)

    monkeypatch.setattr(runtime, "_call_model", wrapped)


def create_thread(client) -> dict:
    response = client.post("/api/v1/agent/threads", json={})
    response.raise_for_status()
    return response.json()


def send_message(
    client,
    thread_id: str,
    content: str,
    *,
    timeout_seconds: float = 2.0,
) -> dict:
    response = client.post(
        f"/api/v1/agent/threads/{thread_id}/messages",
        data={"content": content},
    )
    response.raise_for_status()
    run = response.json()
    if run.get("status") != "running":
        return run

    run_id = run["id"]
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        run_response = client.get(f"/api/v1/agent/runs/{run_id}")
        run_response.raise_for_status()
        run = run_response.json()
        if run.get("status") != "running":
            return run
        time.sleep(0.01)

    raise AssertionError("Timed out waiting for agent run to complete")


def test_settings_endpoint_returns_effective_defaults(client):
    from backend.config import get_settings

    response = client.get("/api/v1/settings")
    response.raise_for_status()
    payload = response.json()

    settings = get_settings()
    assert payload["current_user_name"] == settings.current_user_name
    assert payload["user_memory"] is None
    assert payload["default_currency_code"] == settings.default_currency_code
    assert payload["dashboard_currency_code"] == settings.dashboard_currency_code
    assert payload["agent_model"] == settings.agent_model
    assert payload["overrides"]["user_memory"] is None
    assert payload["overrides"]["agent_model"] is None


def test_settings_model_override_and_clear(client):
    set_override = client.patch("/api/v1/settings", json={"agent_model": "openai/gpt-4.1-mini"})
    set_override.raise_for_status()
    set_payload = set_override.json()
    assert set_payload["agent_model"] == "openai/gpt-4.1-mini"
    assert set_payload["overrides"]["agent_model"] == "openai/gpt-4.1-mini"

    clear_override = client.patch("/api/v1/settings", json={"agent_model": ""})
    clear_override.raise_for_status()
    clear_payload = clear_override.json()
    assert clear_payload["agent_model"] == "openrouter/qwen/qwen3.5-27b"
    assert clear_payload["overrides"]["agent_model"] is None


def test_settings_agent_provider_config_masks_api_key_in_response(client):
    response = client.patch(
        "/api/v1/settings",
        json={
            "agent_base_url": "https://api.example.com/v1",
            "agent_api_key": "sk-test-provider-key",
        },
    )
    response.raise_for_status()
    payload = response.json()

    assert payload["agent_base_url"] == "https://api.example.com/v1"
    assert payload["agent_api_key_configured"] is True
    assert payload["overrides"]["agent_base_url"] == "https://api.example.com/v1"
    assert payload["overrides"]["agent_api_key_configured"] is True
    assert "agent_api_key" not in payload
    assert "agent_api_key" not in payload["overrides"]


def test_settings_agent_base_url_rejects_non_public_ip_hosts(client):
    blocked = [
        "http://127.0.0.2/v1",
        "http://10.0.0.5/v1",
        "http://[::1]:8080/v1",
    ]
    for value in blocked:
        response = client.patch("/api/v1/settings", json={"agent_base_url": value})
        assert response.status_code == 422, value


def test_settings_agent_api_key_rejects_masked_sentinel(client):
    response = client.patch("/api/v1/settings", json={"agent_api_key": "***masked***"})
    assert response.status_code == 422


def test_settings_user_memory_override_and_clear(client):
    memory_text = "Prefers terse answers.\nUses CAD unless stated otherwise."
    set_override = client.patch("/api/v1/settings", json={"user_memory": memory_text})
    set_override.raise_for_status()
    set_payload = set_override.json()
    assert set_payload["user_memory"] == memory_text
    assert set_payload["overrides"]["user_memory"] == memory_text

    clear_override = client.patch("/api/v1/settings", json={"user_memory": " \n  "})
    clear_override.raise_for_status()
    clear_payload = clear_override.json()
    assert clear_payload["user_memory"] is None
    assert clear_payload["overrides"]["user_memory"] is None


def test_settings_override_updates_agent_model_for_new_runs(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Configured model applied."},
    )
    response = client.patch(
        "/api/v1/settings",
        json={
            "agent_model": "openai/gpt-4.1-mini",
            "agent_max_steps": 12,
        },
    )
    response.raise_for_status()
    payload = response.json()
    assert payload["agent_model"] == "openai/gpt-4.1-mini"
    assert payload["agent_max_steps"] == 12

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Hello model")
    assert run["status"] == "completed"
    assert run["model_name"] == "openai/gpt-4.1-mini"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert detail["configured_model_name"] == "openai/gpt-4.1-mini"


def test_default_currency_override_applies_to_agent_entry_proposals_and_apply(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Entry proposal prepared."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entry",
                        "arguments": json.dumps(
                            {
                                "kind": "EXPENSE",
                                "date": "2026-02-10",
                                "name": "Settings Currency Test",
                                "amount_minor": 1435,
                                "from_entity": "Main Checking",
                                "to_entity": "Cafe",
                                "tags": ["food"],
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    update_response = client.patch("/api/v1/settings", json={"default_currency_code": "eur"})
    update_response.raise_for_status()
    assert update_response.json()["default_currency_code"] == "EUR"

    for entity_name in ("Main Checking", "Cafe"):
        entity_response = client.post("/api/v1/entities", json={"name": entity_name})
        entity_response.raise_for_status()
    tag_response = client.post("/api/v1/tags", json={"name": "food"})
    tag_response.raise_for_status()

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Please add the cafe expense.")
    assert run["status"] == "completed"
    assert run["change_items"]

    proposed_item = run["change_items"][0]
    assert proposed_item["payload_json"]["currency_code"] == "EUR"

    approve_response = client.post(f"/api/v1/agent/change-items/{proposed_item['id']}/approve", json={})
    approve_response.raise_for_status()
    approved_payload = approve_response.json()
    assert approved_payload["status"] == "APPLIED"

    entries_response = client.get("/api/v1/entries", params={"source": "Settings Currency Test"})
    entries_response.raise_for_status()
    entries_payload = entries_response.json()
    assert entries_payload["total"] == 1
    assert entries_payload["items"][0]["currency_code"] == "EUR"


def test_dashboard_currency_override_changes_dashboard_currency(client):
    response = client.patch("/api/v1/settings", json={"dashboard_currency_code": "USD"})
    response.raise_for_status()

    dashboard_response = client.get("/api/v1/dashboard", params={"month": "2026-02"})
    dashboard_response.raise_for_status()
    payload = dashboard_response.json()
    assert payload["currency_code"] == "USD"
