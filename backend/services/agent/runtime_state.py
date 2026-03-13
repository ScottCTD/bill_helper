# CALLING SPEC:
# - Purpose: implement focused service logic for `runtime_state`.
# - Inputs: callers that import `backend/services/agent/runtime_state.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `runtime_state`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.enums_agent import (
    AgentMessageRole,
    AgentRunEventSource,
    AgentRunEventType,
    AgentRunStatus,
    AgentToolCallStatus,
)
from backend.models_agent import (
    AgentChangeItem,
    AgentMessage,
    AgentRun,
    AgentRunEvent,
    AgentThread,
    AgentToolCall,
)
from backend.services.agent.protocol_helpers import decode_tool_call
from backend.services.agent.tool_args.shared import INTERMEDIATE_UPDATE_TOOL_NAME
from backend.services.agent.tool_types import ToolExecutionResult


@dataclass(slots=True)
class PreparedToolCall:
    tool_call: dict[str, Any]
    tool_name: str
    arguments: dict[str, Any]
    raw_arguments: str | None = None
    decode_error: str | None = None
    persisted_row: AgentToolCall | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def persist_final_message(
    db: Session,
    thread: AgentThread,
    run: AgentRun,
    content: str,
    *,
    status: AgentRunStatus,
    error_text: str | None = None,
    commit: bool = True,
) -> None:
    assistant = AgentMessage(
        thread_id=thread.id,
        role=AgentMessageRole.ASSISTANT,
        content_markdown=content,
    )
    db.add(assistant)
    db.flush()
    run.assistant_message_id = assistant.id
    run.status = status
    run.error_text = error_text
    run.completed_at = utc_now()
    thread.updated_at = utc_now()
    db.add(run)
    db.add(thread)
    if commit:
        db.commit()
    else:
        db.flush()


def load_run_snapshot(db: Session, run_id: str) -> AgentRun:
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
            selectinload(AgentRun.events).selectinload(AgentRunEvent.tool_call),
            selectinload(AgentRun.tool_calls),
            selectinload(AgentRun.change_items).selectinload(
                AgentChangeItem.review_actions
            ),
        )
    )
    if run is None:  # pragma: no cover - defensive guard
        raise RuntimeError("run not found after persistence")
    return run


def _next_run_event_sequence(db: Session, run_id: str) -> int:
    current_max = db.scalar(
        select(func.max(AgentRunEvent.sequence_index)).where(
            AgentRunEvent.run_id == run_id
        )
    )
    return int(current_max or 0) + 1


def persist_run_event(
    db: Session,
    *,
    run: AgentRun,
    event_type: AgentRunEventType,
    source: AgentRunEventSource | None = None,
    message: str | None = None,
    tool_call: AgentToolCall | None = None,
) -> AgentRunEvent:
    event_row = AgentRunEvent(
        run_id=run.id,
        sequence_index=_next_run_event_sequence(db, run.id),
        event_type=event_type,
        source=source,
        message=message,
        tool_call=tool_call,
    )
    db.add(event_row)
    db.flush()
    return event_row


def queue_tool_call_record(
    db: Session,
    *,
    run: AgentRun,
    tool_call: dict[str, Any],
) -> PreparedToolCall:
    decoded = decode_tool_call(tool_call)
    tool_name = decoded.tool_name or "(unknown)"
    if tool_name == INTERMEDIATE_UPDATE_TOOL_NAME:
        return PreparedToolCall(
            tool_call=tool_call,
            tool_name=tool_name,
            arguments=decoded.arguments,
            raw_arguments=decoded.raw_arguments,
            decode_error=decoded.decode_error,
            persisted_row=None,
        )

    tool_row = AgentToolCall(
        run_id=run.id,
        llm_tool_call_id=str(tool_call.get("id") or "") or None,
        tool_name=tool_name,
        input_json=decoded.arguments,
        output_json={},
        output_text="",
        status=AgentToolCallStatus.QUEUED,
    )
    db.add(tool_row)
    db.flush()
    return PreparedToolCall(
        tool_call=tool_call,
        tool_name=tool_name,
        arguments=decoded.arguments,
        raw_arguments=decoded.raw_arguments,
        decode_error=decoded.decode_error,
        persisted_row=tool_row,
    )


def mark_tool_call_running(db: Session, tool_call: AgentToolCall) -> None:
    tool_call.status = AgentToolCallStatus.RUNNING
    tool_call.started_at = utc_now()
    db.add(tool_call)
    db.flush()


def finalize_tool_call_success(
    db: Session,
    *,
    tool_call: AgentToolCall,
    result: ToolExecutionResult,
) -> None:
    tool_call.output_json = result.output_json
    tool_call.output_text = result.output_text
    tool_call.status = AgentToolCallStatus.OK
    tool_call.completed_at = utc_now()
    db.add(tool_call)
    db.flush()


def finalize_tool_call_error(
    db: Session,
    *,
    tool_call: AgentToolCall,
    result: ToolExecutionResult,
) -> None:
    tool_call.output_json = result.output_json
    tool_call.output_text = result.output_text
    tool_call.status = AgentToolCallStatus.ERROR
    tool_call.completed_at = utc_now()
    db.add(tool_call)
    db.flush()


def cancel_incomplete_tool_calls(db: Session, run: AgentRun) -> list[AgentRunEvent]:
    incomplete_calls = list(
        db.scalars(
            select(AgentToolCall)
            .where(
                AgentToolCall.run_id == run.id,
                AgentToolCall.status.in_(
                    [AgentToolCallStatus.QUEUED, AgentToolCallStatus.RUNNING]
                ),
            )
            .order_by(AgentToolCall.created_at)
        )
    )
    cancelled_events: list[AgentRunEvent] = []
    for tool_call in incomplete_calls:
        tool_call.status = AgentToolCallStatus.CANCELLED
        tool_call.completed_at = tool_call.completed_at or utc_now()
        db.add(tool_call)
        cancelled_events.append(
            persist_run_event(
                db,
                run=run,
                event_type=AgentRunEventType.TOOL_CALL_CANCELLED,
                tool_call=tool_call,
            )
        )
    return cancelled_events


def _normalize_reasoning_message(message: str) -> str | None:
    normalized = message.strip()
    return normalized or None


def record_reasoning_update_event(
    db: Session,
    *,
    run: AgentRun,
    message: str,
    source: AgentRunEventSource,
) -> AgentRunEvent | None:
    normalized_message = _normalize_reasoning_message(message)
    if normalized_message is None:
        return None
    return persist_run_event(
        db,
        run=run,
        event_type=AgentRunEventType.REASONING_UPDATE,
        source=source,
        message=normalized_message,
    )


def _reasoning_source_from_value(value: Any) -> AgentRunEventSource:
    if value == AgentRunEventSource.MODEL_REASONING.value:
        return AgentRunEventSource.MODEL_REASONING
    if value == AgentRunEventSource.ASSISTANT_CONTENT.value:
        return AgentRunEventSource.ASSISTANT_CONTENT
    return AgentRunEventSource.TOOL_CALL


def extract_reasoning_from_tool_result(
    result: ToolExecutionResult,
    arguments: dict[str, Any],
) -> tuple[str | None, AgentRunEventSource]:
    output_json = result.output_json if isinstance(result.output_json, dict) else {}
    output_message = output_json.get("message")
    if isinstance(output_message, str):
        normalized_output = output_message.strip()
        if normalized_output:
            return normalized_output, _reasoning_source_from_value(
                output_json.get("source") or arguments.get("source")
            )

    input_message = arguments.get("message")
    if isinstance(input_message, str):
        normalized_input = input_message.strip()
        if normalized_input:
            return normalized_input, _reasoning_source_from_value(
                output_json.get("source") or arguments.get("source")
            )
    return None, _reasoning_source_from_value(
        output_json.get("source") or arguments.get("source")
    )


def tool_result_llm_message(
    prepared_tool_call: PreparedToolCall, result: ToolExecutionResult
) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": prepared_tool_call.tool_call.get("id"),
        "name": prepared_tool_call.tool_name,
        "content": result.output_text,
    }


def ensure_run_started_event(db: Session, run: AgentRun) -> AgentRunEvent | None:
    existing_event = db.scalar(
        select(AgentRunEvent.id)
        .where(
            AgentRunEvent.run_id == run.id,
            AgentRunEvent.event_type == AgentRunEventType.RUN_STARTED,
        )
        .limit(1)
    )
    if existing_event is not None:
        return None
    return persist_run_event(db, run=run, event_type=AgentRunEventType.RUN_STARTED)


def run_has_terminal_event(db: Session, run_id: str) -> bool:
    return (
        db.scalar(
            select(AgentRunEvent.id)
            .where(
                AgentRunEvent.run_id == run_id,
                AgentRunEvent.event_type.in_(
                    [AgentRunEventType.RUN_COMPLETED, AgentRunEventType.RUN_FAILED]
                ),
            )
            .limit(1)
        )
        is not None
    )


def apply_usage_totals_to_run(run: AgentRun, totals: dict[str, int | None]) -> None:
    run.input_tokens = totals["input_tokens"]
    run.output_tokens = totals["output_tokens"]
    run.cache_read_tokens = totals["cache_read_tokens"]
    run.cache_write_tokens = totals["cache_write_tokens"]


def events_after_sequence(
    db: Session, run_id: str, sequence_index: int
) -> list[AgentRunEvent]:
    return list(
        db.scalars(
            select(AgentRunEvent)
            .where(
                AgentRunEvent.run_id == run_id,
                AgentRunEvent.sequence_index > sequence_index,
            )
            .order_by(AgentRunEvent.sequence_index)
        )
    )
