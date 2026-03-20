# CALLING SPEC:
# - Purpose: verify agent review approval respects create_tag dependencies (pending, rejected, implicit).
# - Inputs: pytest fixtures and helpers that import this module.
# - Outputs: tests asserting HTTP and dependency behavior.
# - Side effects: uses the test database via API client.
from __future__ import annotations

from backend.tests.agent_test_utils import create_thread, patch_model, send_message


def _ensure_entities(client) -> None:
    for entity_name in ("Main Checking", "Cafe"):
        entity_response = client.post("/api/v1/entities", json={"name": entity_name})
        entity_response.raise_for_status()


def test_entry_approve_blocked_until_pending_create_tag_resolved(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "Proposals only."})
    _ensure_entities(client)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Tag dependency test.")
    assert run["status"] == "completed"
    run_id = run["id"]
    headers = {"X-Bill-Helper-Agent-Run-Id": run_id}

    tag_proposal = client.post(
        f"/api/v1/agent/threads/{thread['id']}/proposals",
        headers=headers,
        json={
            "change_type": "create_tag",
            "payload_json": {"name": "pending-tag", "type": "daily"},
        },
    )
    tag_proposal.raise_for_status()
    tag_item = tag_proposal.json()

    entry_proposal = client.post(
        f"/api/v1/agent/threads/{thread['id']}/proposals",
        headers=headers,
        json={
            "change_type": "create_entry",
            "payload_json": {
                "kind": "EXPENSE",
                "date": "2026-02-10",
                "name": "Tagged lunch",
                "amount_minor": 500,
                "from_entity": "Main Checking",
                "to_entity": "Cafe",
                "tags": ["pending-tag"],
            },
        },
    )
    entry_proposal.raise_for_status()
    entry_item = entry_proposal.json()

    block = client.post(
        f"/api/v1/agent/change-items/{entry_item['proposal_id']}/approve",
        json={},
    )
    assert block.status_code == 422
    assert "create_tag" in block.json()["detail"].lower()
    assert "pending-tag" in block.json()["detail"]

    approve_tag = client.post(
        f"/api/v1/agent/change-items/{tag_item['proposal_id']}/approve",
        json={},
    )
    approve_tag.raise_for_status()
    assert approve_tag.json()["status"] == "APPLIED"

    approve_entry = client.post(
        f"/api/v1/agent/change-items/{entry_item['proposal_id']}/approve",
        json={},
    )
    approve_entry.raise_for_status()
    assert approve_entry.json()["status"] == "APPLIED"


def test_entry_approve_allows_implicit_tag_when_no_pending_create_tag(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "Proposals only."})
    _ensure_entities(client)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Implicit tag test.")
    assert run["status"] == "completed"
    headers = {"X-Bill-Helper-Agent-Run-Id": run["id"]}

    entry_proposal = client.post(
        f"/api/v1/agent/threads/{thread['id']}/proposals",
        headers=headers,
        json={
            "change_type": "create_entry",
            "payload_json": {
                "kind": "EXPENSE",
                "date": "2026-02-11",
                "name": "Implicit tag entry",
                "amount_minor": 300,
                "from_entity": "Main Checking",
                "to_entity": "Cafe",
                "tags": ["implicit-only"],
            },
        },
    )
    entry_proposal.raise_for_status()
    entry_item = entry_proposal.json()

    approve_entry = client.post(
        f"/api/v1/agent/change-items/{entry_item['proposal_id']}/approve",
        json={},
    )
    approve_entry.raise_for_status()
    assert approve_entry.json()["status"] == "APPLIED"


def test_entry_approve_blocked_when_create_tag_was_rejected(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "Proposals only."})
    _ensure_entities(client)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Rejected tag dependency test.")
    assert run["status"] == "completed"
    headers = {"X-Bill-Helper-Agent-Run-Id": run["id"]}

    tag_proposal = client.post(
        f"/api/v1/agent/threads/{thread['id']}/proposals",
        headers=headers,
        json={
            "change_type": "create_tag",
            "payload_json": {"name": "rejected-tag", "type": "daily"},
        },
    )
    tag_proposal.raise_for_status()
    tag_item = tag_proposal.json()

    entry_proposal = client.post(
        f"/api/v1/agent/threads/{thread['id']}/proposals",
        headers=headers,
        json={
            "change_type": "create_entry",
            "payload_json": {
                "kind": "EXPENSE",
                "date": "2026-02-12",
                "name": "Depends on rejected tag",
                "amount_minor": 400,
                "from_entity": "Main Checking",
                "to_entity": "Cafe",
                "tags": ["rejected-tag"],
            },
        },
    )
    entry_proposal.raise_for_status()
    entry_item = entry_proposal.json()

    reject_tag = client.post(
        f"/api/v1/agent/change-items/{tag_item['proposal_id']}/reject",
        json={},
    )
    reject_tag.raise_for_status()
    assert reject_tag.json()["status"] == "REJECTED"

    block = client.post(
        f"/api/v1/agent/change-items/{entry_item['proposal_id']}/approve",
        json={},
    )
    assert block.status_code == 422
    detail = block.json()["detail"].lower()
    assert "rejected" in detail or "failed" in detail
    assert "rejected-tag" in block.json()["detail"]
