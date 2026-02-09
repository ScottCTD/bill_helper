from __future__ import annotations

import json
import time


def create_thread(client) -> dict:
    response = client.post("/api/v1/agent/threads", json={})
    response.raise_for_status()
    return response.json()


def send_message(
    client,
    thread_id: str,
    content: str,
    *,
    wait_for_completion: bool = True,
    timeout_seconds: float = 2.0,
) -> dict:
    response = client.post(
        f"/api/v1/agent/threads/{thread_id}/messages",
        data={"content": content},
    )
    response.raise_for_status()
    run = response.json()
    if not wait_for_completion or run.get("status") != "running":
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


def patch_model(monkeypatch, handler):
    from backend.services.agent import runtime

    monkeypatch.setattr(runtime, "_call_openrouter", handler)


def test_thread_history_and_final_assistant_message(client, monkeypatch):
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Here is the final answer with no proposals."},
    )
    thread = create_thread(client)
    run = send_message(client, thread["id"], "What happened this month?")

    assert run["status"] == "completed"
    assert run["assistant_message_id"] is not None
    assert run["change_items"] == []

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]


def test_thread_detail_includes_configured_model_name(client):
    from backend.config import get_settings

    thread = create_thread(client)
    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()

    assert detail["configured_model_name"] == get_settings().agent_model


def test_default_agent_model_is_openai_gpt_5_nano():
    from backend.config import get_settings

    assert get_settings().agent_model == "openai/gpt-5-nano"


def test_system_prompt_requires_duplicate_then_reconcile_then_propose_entries():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    duplicate_phrase = "Before proposing any entry, check for duplicates"
    reconcile_phrase = "list existing tags and entities, then propose missing tags/entities first"
    propose_phrase = "Only after duplicate checks and tag/entity reconciliation, propose entries"

    assert duplicate_phrase in prompt
    assert reconcile_phrase in prompt
    assert propose_phrase in prompt
    assert prompt.index(duplicate_phrase) < prompt.index(reconcile_phrase) < prompt.index(propose_phrase)


def test_system_prompt_allows_concise_final_message_without_empty_review_footer():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    concise_phrase = "Final message should prioritize a concise direct answer"
    conditional_pending_phrase = "Include pending review item ids only when pending items exist"

    assert concise_phrase in prompt
    assert conditional_pending_phrase in prompt
    assert "Final message must include: direct answer, tools used (high level), and pending review item ids." not in prompt


def test_run_persists_tool_calls(client, monkeypatch):
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_list_tags",
                    "type": "function",
                    "function": {"name": "list_tags", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "assistant",
            "content": "I checked tags and found no pending proposals.",
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "list_tags"
    assert run["tool_calls"][0]["status"] == "ok"

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    payload = run_detail.json()
    assert payload["assistant_message_id"] == run["assistant_message_id"]
    assert len(payload["tool_calls"]) == 1


def test_final_message_strips_empty_pending_review_footer(client, monkeypatch):
    patch_model(
        monkeypatch,
        lambda _messages: {
            "role": "assistant",
            "content": (
                "Here is your dashboard summary.\n\n"
                "Tools used (high level): get_dashboard_summary (dashboard snapshot for 2026-02) "
                "Pending review item ids: []"
            ),
        },
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Show dashboard")
    assert run["status"] == "completed"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assistant_messages = [message for message in detail["messages"] if message["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assistant_content = assistant_messages[0]["content_markdown"]
    assert "Pending review item ids: []" not in assistant_content
    assert "Tools used (high level):" not in assistant_content


def test_send_message_returns_running_while_agent_executes(client, monkeypatch):
    def slow_model(_messages):
        time.sleep(0.35)
        return {"role": "assistant", "content": "Done."}

    patch_model(monkeypatch, slow_model)
    thread = create_thread(client)

    response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/messages",
        data={"content": "hello"},
    )
    response.raise_for_status()
    run = response.json()

    assert run["status"] == "running"
    assert run["assistant_message_id"] is None

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
        run_response.raise_for_status()
        payload = run_response.json()
        if payload["status"] != "running":
            assert payload["status"] == "completed"
            assert payload["assistant_message_id"] is not None
            return
        time.sleep(0.02)

    raise AssertionError("Run did not complete in time")


def test_run_accumulates_usage_tokens_across_steps(client, monkeypatch):
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_list_tags",
                    "type": "function",
                    "function": {"name": "list_tags", "arguments": "{}"},
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 3,
                "cache_read_tokens": 2,
                "cache_write_tokens": 1,
            },
        },
        {
            "role": "assistant",
            "content": "I checked tags and found no pending proposals.",
            "usage": {
                "input_tokens": 5,
                "output_tokens": 7,
                "cache_read_tokens": 0,
                "cache_write_tokens": 4,
            },
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.")

    assert run["status"] == "completed"
    assert run["input_tokens"] == 15
    assert run["output_tokens"] == 10
    assert run["cache_read_tokens"] == 2
    assert run["cache_write_tokens"] == 5
    assert "input_cost_usd" in run
    assert "output_cost_usd" in run
    assert "total_cost_usd" in run

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    payload = run_detail.json()
    assert payload["input_tokens"] == 15
    assert payload["output_tokens"] == 10
    assert payload["cache_read_tokens"] == 2
    assert payload["cache_write_tokens"] == 5
    assert "input_cost_usd" in payload
    assert "output_cost_usd" in payload
    assert "total_cost_usd" in payload


def test_run_usage_fields_are_null_when_usage_unavailable(client, monkeypatch):
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Here is the final answer with no usage metadata."},
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "What happened this month?")

    assert run["status"] == "completed"
    assert run["input_tokens"] is None
    assert run["output_tokens"] is None
    assert run["cache_read_tokens"] is None
    assert run["cache_write_tokens"] is None


def test_run_handles_unknown_tool_calls_as_error(client, monkeypatch):
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_unknown",
                    "type": "function",
                    "function": {"name": "unknown_tool", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "assistant",
            "content": "I could not use that tool, but completed the run.",
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Please call a missing tool")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "unknown_tool"
    assert run["tool_calls"][0]["status"] == "error"
    assert run["tool_calls"][0]["output_json"]["summary"] == "unknown tool 'unknown_tool'"


def test_proposal_creation_for_each_change_type(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Done. Please review pending items."}
        user_message = next(message for message in reversed(messages) if message["role"] == "user")
        content = user_message["content"] if isinstance(user_message["content"], str) else ""
        if "tag" in content:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_propose_tag",
                        "type": "function",
                        "function": {
                            "name": "propose_create_tag",
                            "arguments": json.dumps(
                                {
                                    "name": "groceries",
                                    "color": "#22aa99",
                                    "rationale": "Recurring spend category",
                                }
                            ),
                        },
                    }
                ],
            }
        if "entity" in content:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_propose_entity",
                        "type": "function",
                        "function": {
                            "name": "propose_create_entity",
                            "arguments": json.dumps(
                                {
                                    "name": "Costco",
                                    "category": "merchant",
                                    "rationale": "Merchant appears in receipts",
                                }
                            ),
                        },
                    }
                ],
            }
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
                                "occurred_at": "2026-01-03",
                                "name": "Coffee",
                                "amount_minor": 550,
                                "currency_code": "USD",
                                "tags": ["food"],
                                "rationale": "Receipt has coffee charge",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run_tag = send_message(client, thread["id"], "Please propose a new tag.")
    run_entity = send_message(client, thread["id"], "Please propose a new entity.")
    run_entry = send_message(client, thread["id"], "Please propose a new entry.")

    assert run_tag["change_items"][0]["change_type"] == "create_tag"
    assert run_entity["change_items"][0]["change_type"] == "create_entity"
    assert run_entry["change_items"][0]["change_type"] == "create_entry"
    assert run_tag["change_items"][0]["status"] == "PENDING_REVIEW"
    assert run_entity["change_items"][0]["status"] == "PENDING_REVIEW"
    assert run_entry["change_items"][0]["status"] == "PENDING_REVIEW"


def test_approve_and_reapprove_conflict(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Tag proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_tag",
                    "type": "function",
                    "function": {
                        "name": "propose_create_tag",
                        "arguments": json.dumps(
                            {
                                "name": "subscriptions",
                                "rationale": "Track recurring services",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose tag subscriptions")
    item_id = run["change_items"][0]["id"]

    approve_response = client.post(f"/api/v1/agent/change-items/{item_id}/approve", json={})
    approve_response.raise_for_status()
    approved = approve_response.json()
    assert approved["status"] == "APPLIED"
    assert approved["applied_resource_type"] == "tag"
    tags = client.get("/api/v1/tags").json()
    assert any(tag["name"] == "subscriptions" for tag in tags)

    second_approve = client.post(f"/api/v1/agent/change-items/{item_id}/approve", json={})
    assert second_approve.status_code == 409


def test_reject_flow(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Entity proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entity",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entity",
                        "arguments": json.dumps(
                            {
                                "name": "Temp Vendor",
                                "category": "merchant",
                                "rationale": "Potential vendor from OCR",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose entity Temp Vendor")
    item_id = run["change_items"][0]["id"]

    reject_response = client.post(f"/api/v1/agent/change-items/{item_id}/reject", json={"note": "Wrong merchant"})
    reject_response.raise_for_status()
    rejected = reject_response.json()
    assert rejected["status"] == "REJECTED"

    entities = client.get("/api/v1/entities").json()
    assert all(entity["name"] != "Temp Vendor" for entity in entities)


def test_entry_approve_applies_entry_and_allows_override(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Entry proposal created."}
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
                                "occurred_at": "2026-01-09",
                                "name": "Lunch draft",
                                "amount_minor": 1800,
                                "currency_code": "USD",
                                "tags": ["food"],
                                "rationale": "Receipt text extraction",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose an entry for lunch")
    item_id = run["change_items"][0]["id"]

    approve_response = client.post(
        f"/api/v1/agent/change-items/{item_id}/approve",
        json={
            "payload_override": {
                "kind": "EXPENSE",
                "occurred_at": "2026-01-09",
                "name": "Lunch confirmed by reviewer",
                "amount_minor": 1800,
                "currency_code": "USD",
                "tags": ["food", "team"],
            }
        },
    )
    approve_response.raise_for_status()
    approved = approve_response.json()
    assert approved["status"] == "APPLIED"
    assert approved["applied_resource_type"] == "entry"

    entries = client.get("/api/v1/entries", params={"source": "Lunch confirmed by reviewer"})
    entries.raise_for_status()
    payload = entries.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Lunch confirmed by reviewer"
    assert "status" not in payload["items"][0]


def test_entry_approve_apply_failure_marks_item_failed(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Entry proposal created."}
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
                                "occurred_at": "2026-01-10",
                                "name": "Broken account reference",
                                "amount_minor": 1200,
                                "currency_code": "USD",
                                "account_id": "missing-account-id",
                                "rationale": "Account id came from OCR",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose entry with account")
    item_id = run["change_items"][0]["id"]

    approve_response = client.post(
        f"/api/v1/agent/change-items/{item_id}/approve",
        json={"note": "attempt apply"},
    )
    assert approve_response.status_code == 422
    assert "Account not found" in approve_response.text

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    refreshed_item = next(item for item in run_detail.json()["change_items"] if item["id"] == item_id)
    assert refreshed_item["status"] == "APPLY_FAILED"
    assert "apply failed: Account not found" in (refreshed_item["review_note"] or "")
    assert any(action["action"] == "approve" for action in refreshed_item["review_actions"])


def test_requires_openrouter_key_for_send_message(client):
    from backend.config import get_settings

    settings = get_settings()
    original_key = settings.openrouter_api_key
    try:
        settings.openrouter_api_key = None
        thread = create_thread(client)
        response = client.post(
            f"/api/v1/agent/threads/{thread['id']}/messages",
            data={"content": "hello"},
        )
        assert response.status_code == 503
    finally:
        settings.openrouter_api_key = original_key
