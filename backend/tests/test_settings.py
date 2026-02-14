from __future__ import annotations

import json
import time
from inspect import signature


def patch_model(monkeypatch, handler):
    from backend.services.agent import runtime

    accepts_db = len(signature(handler).parameters) > 1

    def wrapped(messages, db):
        if accepts_db:
            return handler(messages, db)
        return handler(messages)

    monkeypatch.setattr(runtime, "_call_openrouter", wrapped)


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
    assert payload["default_currency_code"] == settings.default_currency_code
    assert payload["dashboard_currency_code"] == settings.dashboard_currency_code
    assert payload["agent_model"] == settings.agent_model
    assert payload["openrouter_api_key_source"] == "server_default"
    assert payload["openrouter_api_key_configured"] is True
    assert payload["overrides"]["openrouter_api_key_override_set"] is False


def test_settings_api_key_override_and_clear(client):
    set_override = client.patch("/api/v1/settings", json={"openrouter_api_key": "user-specific-key"})
    set_override.raise_for_status()
    set_payload = set_override.json()
    assert set_payload["openrouter_api_key_source"] == "override"
    assert set_payload["overrides"]["openrouter_api_key_override_set"] is True

    clear_override = client.patch("/api/v1/settings", json={"openrouter_api_key": ""})
    clear_override.raise_for_status()
    clear_payload = clear_override.json()
    assert clear_payload["openrouter_api_key_source"] == "server_default"
    assert clear_payload["openrouter_api_key_configured"] is True
    assert clear_payload["overrides"]["openrouter_api_key_override_set"] is False


def test_settings_override_updates_agent_model_for_new_runs(client, monkeypatch):
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
