# CALLING SPEC:
# - Purpose: verify `approval_policy` is persisted on runs and returned on API responses.
# - Inputs: pytest `client` fixture and `patch_model` for deterministic agent runs.
# - Outputs: assertions on run JSON.
# - Side effects: uses the managed test database.
from __future__ import annotations

from backend.enums_agent import AgentApprovalPolicy
from backend.models_agent import _coerce_approval_policy
from backend.tests.agent_test_utils import create_thread, patch_model, send_message


def test_coerce_approval_policy_accepts_legacy_db_casing() -> None:
    assert _coerce_approval_policy("YOLO") == AgentApprovalPolicy.YOLO
    assert _coerce_approval_policy("DEFAULT") == AgentApprovalPolicy.DEFAULT
    assert _coerce_approval_policy("yolo") == AgentApprovalPolicy.YOLO
    assert _coerce_approval_policy("default") == AgentApprovalPolicy.DEFAULT


def test_message_send_persists_approval_policy(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "done."})
    thread = create_thread(client)
    response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/messages",
        data={
            "content": "hi",
            "approval_policy": "yolo",
            "attachments_use_ocr": "true",
            "surface": "app",
        },
    )
    response.raise_for_status()
    run = response.json()
    assert run["approval_policy"] == "yolo"

    run = send_message(client, thread["id"], "again", approval_policy="default", wait_for_completion=True)
    assert run["approval_policy"] == "default"
