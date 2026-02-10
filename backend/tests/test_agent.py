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


def test_default_agent_model_is_google_gemini_3_flash_preview():
    from backend.config import get_settings

    assert get_settings().agent_model == "google/gemini-3-flash-preview"


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


def test_system_prompt_includes_error_recovery_and_no_domain_ids():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "# Bill Helper System Prompt" in prompt
    assert "## Rules" in prompt
    assert "append-only policies" not in prompt
    assert "You are the Bill Helper assistant." in prompt
    assert "Final message should prioritize a concise direct answer" in prompt
    assert "Include pending review item ids only when pending items exist" not in prompt
    assert "Do not use domain IDs in proposals" in prompt
    assert "If a tool returns an ERROR" in prompt


def test_system_prompt_includes_current_date_tag():
    from datetime import date

    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt(current_date=date(2026, 2, 10))
    assert "## Current Date (UTC)\n2026-02-10" in prompt


def test_system_prompt_includes_current_user_account_context(client, monkeypatch):
    create_account_response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Main Checking",
            "institution": "Bank Co",
            "account_type": "checking",
            "currency_code": "usd",
            "is_active": True,
        },
    )
    create_account_response.raise_for_status()

    captured_messages: list[list[dict]] = []

    def model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "ok"}

    patch_model(monkeypatch, model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "hello")
    assert run["status"] == "completed"
    assert captured_messages

    system_message = captured_messages[-1][0]
    assert system_message.get("role") == "system"
    system_content = str(system_message.get("content", ""))
    assert "## Current User Context" in system_content
    assert "accounts_count: 1" in system_content
    assert "name=Main Checking" in system_content
    assert "currency=USD" in system_content


def test_tool_catalog_removes_legacy_read_tools_and_adds_crud_proposals():
    from backend.services.agent.tools import build_openai_tool_schemas

    names = [tool["function"]["name"] for tool in build_openai_tool_schemas()]
    assert "list_accounts" not in names
    assert "search_entries" not in names
    assert "list_entries" in names
    assert "propose_update_entry" in names
    assert "propose_delete_entry" in names
    assert "propose_update_tag" in names
    assert "propose_delete_tag" in names
    assert "propose_update_entity" in names
    assert "propose_delete_entity" in names


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


def test_proposal_creation_for_each_create_change_type(client, monkeypatch):
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
                                    "category": "daily",
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
                                "date": "2026-01-03",
                                "name": "Coffee",
                                "amount_minor": 550,
                                "currency_code": "USD",
                                "from_entity": "Main Checking",
                                "to_entity": "Coffee Shop",
                                "tags": ["food"],
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread_tag = create_thread(client)
    thread_entity = create_thread(client)
    thread_entry = create_thread(client)
    run_tag = send_message(client, thread_tag["id"], "Please propose a new tag.")
    run_entity = send_message(client, thread_entity["id"], "Please propose a new entity.")
    run_entry = send_message(client, thread_entry["id"], "Please propose a new entry.")

    assert run_tag["change_items"][0]["change_type"] == "create_tag"
    assert run_entity["change_items"][0]["change_type"] == "create_entity"
    assert run_entry["change_items"][0]["change_type"] == "create_entry"
    assert run_tag["change_items"][0]["status"] == "PENDING_REVIEW"
    assert run_entity["change_items"][0]["status"] == "PENDING_REVIEW"
    assert run_entry["change_items"][0]["status"] == "PENDING_REVIEW"
    assert "account_id" not in run_entry["change_items"][0]["payload_json"]


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
                                "category": "recurring",
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
                                "date": "2026-01-09",
                                "name": "Lunch draft",
                                "amount_minor": 1800,
                                "currency_code": "USD",
                                "from_entity": "Main Checking",
                                "to_entity": "Lunch Spot",
                                "tags": ["food"],
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
                "date": "2026-01-09",
                "name": "Lunch confirmed by reviewer",
                "amount_minor": 1800,
                "currency_code": "USD",
                "from_entity": "Main Checking",
                "to_entity": "Lunch Spot",
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
                                "date": "2026-01-10",
                                "name": "Draft entry",
                                "amount_minor": 1200,
                                "currency_code": "USD",
                                "from_entity": "Main Checking",
                                "to_entity": "Store",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose entry")
    item_id = run["change_items"][0]["id"]

    approve_response = client.post(
        f"/api/v1/agent/change-items/{item_id}/approve",
        json={
            "note": "attempt apply",
            "payload_override": {
                "kind": "EXPENSE",
                "date": "2026-01-10",
                "name": "Missing from_entity",
                "amount_minor": 1200,
                "currency_code": "USD",
                "to_entity": "Store",
            },
        },
    )
    assert approve_response.status_code == 422
    assert "from_entity" in approve_response.text

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    refreshed_item = next(item for item in run_detail.json()["change_items"] if item["id"] == item_id)
    assert refreshed_item["status"] == "APPLY_FAILED"
    assert "apply failed" in (refreshed_item["review_note"] or "")
    assert any(action["action"] == "approve" for action in refreshed_item["review_actions"])


def test_update_entry_selector_ambiguity_is_reported_to_agent(client, monkeypatch):
    # Prepare duplicate selector candidates.
    for _ in range(2):
        create_response = client.post(
            "/api/v1/entries",
            json={
                "kind": "EXPENSE",
                "occurred_at": "2026-01-11",
                "name": "Ambiguous Lunch",
                "amount_minor": 2500,
                "currency_code": "USD",
                "from_entity": "Main Checking",
                "to_entity": "Lunch Spot",
                "tags": ["food"],
            },
        )
        create_response.raise_for_status()

    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Selector is ambiguous; please clarify which entry to update."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_update_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_update_entry",
                        "arguments": json.dumps(
                            {
                                "selector": {
                                    "date": "2026-01-11",
                                    "amount_minor": 2500,
                                    "from_entity": "Main Checking",
                                    "to_entity": "Lunch Spot",
                                    "name": "Ambiguous Lunch",
                                },
                                "patch": {
                                    "name": "Ambiguous Lunch (updated)",
                                },
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Update that lunch entry")

    assert run["status"] == "completed"
    assert run["change_items"] == []
    assert len(run["tool_calls"]) == 1
    tool_output = run["tool_calls"][0]["output_json"]
    assert tool_output["status"] == "ERROR"
    assert "ambiguous selector" in tool_output["summary"]


def test_reviewed_items_are_injected_into_followup_turn(client, monkeypatch):
    def first_model(messages):
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
                                "name": "tmp-tag",
                                "category": "tmp",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, first_model)
    thread = create_thread(client)
    first_run = send_message(client, thread["id"], "Create a temporary tag")
    item_id = first_run["change_items"][0]["id"]

    reject_response = client.post(
        f"/api/v1/agent/change-items/{item_id}/reject",
        json={"note": "Use category recurring instead"},
    )
    reject_response.raise_for_status()

    captured_messages: list[list[dict]] = []

    def second_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Acknowledged review feedback."}

    patch_model(monkeypatch, second_model)
    followup_run = send_message(client, thread["id"], "Try again")
    assert followup_run["status"] == "completed"
    assert captured_messages

    history = captured_messages[-1]
    followup_user_messages = [message for message in history if message.get("role") == "user"]
    assert followup_user_messages
    followup_user = followup_user_messages[-1]
    followup_content = followup_user.get("content")
    assert isinstance(followup_content, str)
    assert "Review results from your previous proposals:" in followup_content
    assert "propose_create_tag" in followup_content
    assert "review_action: reject" in followup_content.lower()
    assert "Use category recurring instead" in followup_content
    assert followup_content.index("Review results from your previous proposals:") < followup_content.index("User feedback:")
    assert followup_content.index("User feedback:") < followup_content.index("Try again")


def test_propose_tools_blocked_when_pending_reviews_exist(client, monkeypatch):
    # First run creates a pending proposal and we intentionally skip review.
    def first_model(messages):
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
                        "arguments": json.dumps({"name": "pending-tag", "category": "misc"}),
                    },
                }
            ],
        }

    patch_model(monkeypatch, first_model)
    thread = create_thread(client)
    first_run = send_message(client, thread["id"], "Create tag pending-tag")
    assert first_run["change_items"][0]["status"] == "PENDING_REVIEW"

    # Second run attempts another proposal while first one is still pending.
    def second_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Need review before proposing more changes."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entity",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entity",
                        "arguments": json.dumps({"name": "Blocked Entity", "category": "merchant"}),
                    },
                }
            ],
        }

    patch_model(monkeypatch, second_model)
    second_run = send_message(client, thread["id"], "Create blocked entity")
    assert second_run["status"] == "completed"
    assert second_run["change_items"] == []
    assert len(second_run["tool_calls"]) == 1
    output_json = second_run["tool_calls"][0]["output_json"]
    assert output_json["status"] == "ERROR"
    assert "blocked" in output_json["summary"]


def test_create_entry_uses_default_currency_when_omitted(client, monkeypatch):
    from backend.config import get_settings

    settings = get_settings()
    original_currency = settings.default_currency_code

    try:
        settings.default_currency_code = "CAD"

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
                                    "date": "2026-01-13",
                                    "name": "Transit",
                                    "amount_minor": 450,
                                    "from_entity": "Main Checking",
                                    "to_entity": "Transit Agency",
                                    "tags": ["transport"],
                                }
                            ),
                        },
                    }
                ],
            }

        patch_model(monkeypatch, fake_model)
        thread = create_thread(client)
        run = send_message(client, thread["id"], "Propose transit entry")
        item_id = run["change_items"][0]["id"]

        approve_response = client.post(f"/api/v1/agent/change-items/{item_id}/approve", json={})
        approve_response.raise_for_status()

        entries = client.get("/api/v1/entries", params={"source": "Transit"})
        entries.raise_for_status()
        payload = entries.json()
        assert payload["total"] == 1
        assert payload["items"][0]["currency_code"] == "CAD"
    finally:
        settings.default_currency_code = original_currency


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
