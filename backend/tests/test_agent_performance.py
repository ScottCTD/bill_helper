from __future__ import annotations

import time
from statistics import median

from backend.database import SessionLocal
from backend.enums_agent import AgentMessageRole, AgentRunEventType, AgentRunStatus, AgentToolCallStatus
from backend.models_agent import AgentMessage, AgentRun, AgentRunEvent, AgentThread, AgentToolCall
from backend.models_finance import User


def _seed_tool_heavy_thread(
    *,
    run_count: int = 4,
    tool_calls_per_run: int = 50,
) -> tuple[str, str]:
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.name == "admin").one()
        thread = AgentThread(title="Performance guard thread", owner_user_id=owner.id)
        db.add(thread)
        db.flush()

        first_tool_call_id = ""
        for run_index in range(run_count):
            user_message = AgentMessage(
                thread_id=thread.id,
                role=AgentMessageRole.USER,
                content_markdown=f"User message {run_index}",
            )
            assistant_message = AgentMessage(
                thread_id=thread.id,
                role=AgentMessageRole.ASSISTANT,
                content_markdown="Done.",
            )
            db.add_all([user_message, assistant_message])
            db.flush()

            run = AgentRun(
                thread_id=thread.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                status=AgentRunStatus.COMPLETED,
                model_name="openai/gpt-4.1-mini",
                context_tokens=4_096,
            )
            db.add(run)
            db.flush()

            for tool_index in range(tool_calls_per_run):
                tool_call = AgentToolCall(
                    run_id=run.id,
                    tool_name="list_entries",
                    input_json={
                        "query": f"run-{run_index}-tool-{tool_index}",
                        "filters": ["expense", "cad", "recent"] * 8,
                    },
                    output_json={
                        "status": "ok",
                        "rows": [
                            {
                                "entry_id": f"entry-{row_index}",
                                "name": "x" * 96,
                                "category": "expenses",
                            }
                            for row_index in range(24)
                        ],
                    },
                    output_text="OK\n" + ("result line with details\n" * 80),
                    status=AgentToolCallStatus.OK,
                )
                db.add(tool_call)
                db.flush()

                if not first_tool_call_id:
                    first_tool_call_id = tool_call.id

                db.add_all(
                    [
                        AgentRunEvent(
                            run_id=run.id,
                            sequence_index=(tool_index * 2) + 1,
                            event_type=AgentRunEventType.TOOL_CALL_QUEUED,
                            tool_call_id=tool_call.id,
                        ),
                        AgentRunEvent(
                            run_id=run.id,
                            sequence_index=(tool_index * 2) + 2,
                            event_type=AgentRunEventType.TOOL_CALL_COMPLETED,
                            tool_call_id=tool_call.id,
                        ),
                    ]
                )

        db.commit()
        return thread.id, first_tool_call_id
    finally:
        db.close()


def _median_request_seconds(client, path: str, *, attempts: int = 3) -> tuple[float, bytes]:
    durations: list[float] = []
    last_body = b""
    for _ in range(attempts):
        start = time.perf_counter()
        response = client.get(path)
        elapsed = time.perf_counter() - start
        response.raise_for_status()
        durations.append(elapsed)
        last_body = response.content
    return median(durations), last_body


def test_thread_detail_has_runtime_and_payload_budgets_for_tool_heavy_history(client):
    thread_id, _tool_call_id = _seed_tool_heavy_thread()

    # Warm up to reduce one-time overhead noise before sampling.
    warmup = client.get(f"/api/v1/agent/threads/{thread_id}")
    warmup.raise_for_status()

    median_seconds, body = _median_request_seconds(client, f"/api/v1/agent/threads/{thread_id}", attempts=3)
    median_ms = median_seconds * 1000
    body_bytes = len(body)

    assert median_ms < 750, f"thread detail median latency too high: {median_ms:.1f}ms (budget: <750ms)"
    assert body_bytes < 350_000, f"thread detail payload too large: {body_bytes} bytes (budget: <350000)"


def test_tool_call_detail_has_runtime_budget_and_returns_full_payload(client):
    _thread_id, tool_call_id = _seed_tool_heavy_thread(run_count=2, tool_calls_per_run=30)

    warmup = client.get(f"/api/v1/agent/tool-calls/{tool_call_id}")
    warmup.raise_for_status()

    median_seconds, _body = _median_request_seconds(client, f"/api/v1/agent/tool-calls/{tool_call_id}", attempts=3)
    median_ms = median_seconds * 1000
    assert median_ms < 250, f"tool-call detail median latency too high: {median_ms:.1f}ms (budget: <250ms)"

    response = client.get(f"/api/v1/agent/tool-calls/{tool_call_id}")
    response.raise_for_status()
    payload = response.json()
    assert payload["has_full_payload"] is True
    assert isinstance(payload["input_json"], dict)
    assert isinstance(payload["output_json"], dict)
    assert isinstance(payload["output_text"], str)
