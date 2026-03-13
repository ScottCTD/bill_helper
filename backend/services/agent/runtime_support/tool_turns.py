# CALLING SPEC:
# - Purpose: implement focused service logic for `tool_turns`.
# - Inputs: callers that import `backend/services/agent/runtime_support/tool_turns.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `tool_turns`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

import re
from typing import Any, Callable

from sqlalchemy.orm import Session

from backend.enums_agent import AgentRunEventSource, AgentRunEventType
from backend.models_agent import AgentRun, AgentRunEvent
from backend.services.agent.protocol_helpers import canonicalize_tool_call
from backend.services.agent.runtime_state import (
    PreparedToolCall,
    persist_run_event as _persist_run_event,
    queue_tool_call_record as _queue_tool_call_record,
    record_reasoning_update_event as _record_reasoning_update_event,
)


ContextTokenCalculator = Callable[..., int | None]
RunContextUpdater = Callable[[AgentRun, list[dict[str, Any]]], None]

EMPTY_PENDING_REVIEW_FOOTER_PATTERN = re.compile(
    r"^\s*Tools used \(high level\):.*Pending review item ids:\s*\[\s*\]\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def final_assistant_content(content: str) -> str:
    normalized = content.strip()
    if normalized:
        cleaned = EMPTY_PENDING_REVIEW_FOOTER_PATTERN.sub("", normalized)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if cleaned:
            return cleaned
    return (
        "I completed tool execution but did not receive a final assistant response. "
        "Please review pending items below if any were created."
    )


def update_run_context_tokens(
    *,
    run: AgentRun,
    llm_messages: list[dict[str, Any]],
    calculate_context_tokens: ContextTokenCalculator,
) -> None:
    run.context_tokens = calculate_context_tokens(
        model_name=run.model_name,
        llm_messages=llm_messages,
    )


def prepare_tool_turn(
    db: Session,
    *,
    run: AgentRun,
    llm_messages: list[dict[str, Any]],
    assistant_content: str,
    model_reasoning: str,
    tool_calls: list[dict[str, Any]],
    update_run_context_tokens: RunContextUpdater,
) -> tuple[list[PreparedToolCall], list[AgentRunEvent]]:
    prepared_calls: list[PreparedToolCall] = []
    event_rows: list[AgentRunEvent] = []
    sanitized_tool_calls = [canonicalize_tool_call(tool_call) for tool_call in tool_calls]

    reasoning_event = _record_reasoning_update_event(
        db,
        run=run,
        message=model_reasoning,
        source=AgentRunEventSource.MODEL_REASONING,
    )
    if reasoning_event is not None:
        event_rows.append(reasoning_event)

    llm_messages.append(
        {
            "role": "assistant",
            "content": assistant_content,
            "tool_calls": sanitized_tool_calls,
        }
    )
    assistant_event = _record_reasoning_update_event(
        db,
        run=run,
        message=assistant_content,
        source=AgentRunEventSource.ASSISTANT_CONTENT,
    )
    if assistant_event is not None:
        event_rows.append(assistant_event)

    for tool_call in sanitized_tool_calls:
        prepared_call = _queue_tool_call_record(db, run=run, tool_call=tool_call)
        prepared_calls.append(prepared_call)
        if prepared_call.persisted_row is None:
            continue
        event_rows.append(
            _persist_run_event(
                db,
                run=run,
                event_type=AgentRunEventType.TOOL_CALL_QUEUED,
                tool_call=prepared_call.persisted_row,
            )
        )

    update_run_context_tokens(run=run, llm_messages=llm_messages)
    db.add(run)
    db.commit()
    return prepared_calls, event_rows
