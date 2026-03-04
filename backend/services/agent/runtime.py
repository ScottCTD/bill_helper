from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.enums import (
    AgentMessageRole,
    AgentRunEventSource,
    AgentRunEventType,
    AgentRunStatus,
    AgentToolCallStatus,
)
from backend.models import AgentChangeItem, AgentMessage, AgentRun, AgentRunEvent, AgentThread, AgentToolCall
from backend.services.agent.context_tokens import count_context_tokens
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.model_client import AgentModelError, LiteLLMModelClient, validate_litellm_environment
from backend.services.agent.tools import (
    INTERMEDIATE_UPDATE_TOOL_NAME,
    ToolContext,
    ToolExecutionResult,
    build_openai_tool_schemas,
    execute_tool,
)
from backend.services.runtime_settings import resolve_runtime_settings


USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)
EMPTY_PENDING_REVIEW_FOOTER_PATTERN = re.compile(
    r"^\s*Tools used \(high level\):.*Pending review item ids:\s*\[\s*\]\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRuntimeUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class PreparedToolCall:
    tool_call: dict[str, Any]
    tool_name: str
    arguments: dict[str, Any]
    persisted_row: AgentToolCall | None = None


def ensure_agent_available(db: Session) -> None:
    settings = resolve_runtime_settings(db)
    has_credentials, missing_keys, request_model = validate_litellm_environment(
        model_name=settings.agent_model,
    )
    if has_credentials:
        return
    missing_text = f" Missing keys: {', '.join(missing_keys)}." if missing_keys else ""
    raise AgentRuntimeUnavailable(
        "Agent runtime is not configured. "
        f"Model target: {request_model}.{missing_text} "
        "Provide provider credentials via environment variables for BILL_HELPER_AGENT_MODEL."
    )


def _build_model_client(db: Session) -> LiteLLMModelClient:
    settings = resolve_runtime_settings(db)
    return LiteLLMModelClient(
        model_name=settings.agent_model,
        tools=build_openai_tool_schemas(),
        retry_max_attempts=settings.agent_retry_max_attempts,
        retry_initial_wait_seconds=settings.agent_retry_initial_wait_seconds,
        retry_max_wait_seconds=settings.agent_retry_max_wait_seconds,
        retry_backoff_multiplier=settings.agent_retry_backoff_multiplier,
        langfuse_public_key=settings.langfuse_public_key,
        langfuse_secret_key=settings.langfuse_secret_key,
        langfuse_host=settings.langfuse_host,
    )


def _call_model(
    messages: list[dict[str, Any]],
    db: Session,
    *,
    observability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Kept as a stable seam so tests can monkeypatch model responses.
    return _build_model_client(db).complete(messages, observability=observability)


def _call_model_stream(
    messages: list[dict[str, Any]],
    db: Session,
    *,
    observability: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    # Kept as a stable seam so tests can monkeypatch streaming model responses.
    return _build_model_client(db).complete_stream(messages, observability=observability)


def _model_observability_context(
    *,
    current_user_name: str,
    thread_id: str,
    run_id: str,
    step: int | None = None,
    is_first_run_in_thread: bool = True,
    run_index: int = 1,
) -> dict[str, Any]:
    trace: dict[str, Any] = {
        "trace_id": thread_id,
        "trace_name": "Bill Helper Agent",
        "thread_id": thread_id,
        "run_id": run_id,
        "is_first_run_in_thread": is_first_run_in_thread,
        "run_index": run_index,
    }
    if step is not None:
        trace["step"] = step
    return {
        "user": current_user_name,
        "session_id": thread_id,
        "trace": trace,
    }


def _persist_final_message(
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


def _load_run_snapshot(db: Session, run_id: str) -> AgentRun:
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_calls),
            selectinload(AgentRun.change_items).selectinload(AgentChangeItem.review_actions),
        )
    )
    if run is None:  # pragma: no cover - defensive guard
        raise RuntimeError("run not found after persistence")
    return run


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, str):
        try:
            return json.loads(raw_arguments)
        except (TypeError, ValueError):
            return {}
    try:
        return dict(raw_arguments)
    except (TypeError, ValueError):
        return {}


def _next_run_event_sequence(db: Session, run_id: str) -> int:
    current_max = db.scalar(
        select(func.max(AgentRunEvent.sequence_index)).where(AgentRunEvent.run_id == run_id)
    )
    return int(current_max or 0) + 1


def _persist_run_event(
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
        tool_call_id=tool_call.id if tool_call is not None else None,
    )
    db.add(event_row)
    db.flush()
    return event_row


def _emit_run_event(run: AgentRun, persisted_event: AgentRunEvent) -> dict[str, Any]:
    return {
        "type": "run_event",
        "run_id": run.id,
        "event": {
            "id": persisted_event.id,
            "run_id": persisted_event.run_id,
            "sequence_index": persisted_event.sequence_index,
            "event_type": persisted_event.event_type.value,
            "source": persisted_event.source.value if persisted_event.source is not None else None,
            "message": persisted_event.message,
            "tool_call_id": persisted_event.tool_call_id,
            "created_at": persisted_event.created_at.isoformat(),
        },
    }


def _queue_tool_call_record(
    db: Session,
    *,
    run: AgentRun,
    tool_call: dict[str, Any],
) -> PreparedToolCall:
    function = tool_call.get("function") or {}
    tool_name = str(function.get("name") or "(unknown)")
    arguments = _parse_tool_arguments(function.get("arguments") or "{}")
    if tool_name == INTERMEDIATE_UPDATE_TOOL_NAME:
        return PreparedToolCall(
            tool_call=tool_call,
            tool_name=tool_name,
            arguments=arguments,
            persisted_row=None,
        )

    tool_row = AgentToolCall(
        run_id=run.id,
        llm_tool_call_id=str(tool_call.get("id") or "") or None,
        tool_name=tool_name,
        input_json=arguments,
        output_json={},
        output_text="",
        status=AgentToolCallStatus.QUEUED,
    )
    db.add(tool_row)
    db.flush()
    return PreparedToolCall(
        tool_call=tool_call,
        tool_name=tool_name,
        arguments=arguments,
        persisted_row=tool_row,
    )


def _mark_tool_call_running(db: Session, tool_call: AgentToolCall) -> None:
    tool_call.status = AgentToolCallStatus.RUNNING
    tool_call.started_at = utc_now()
    db.add(tool_call)
    db.flush()


def _finalize_tool_call_success(
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


def _finalize_tool_call_error(
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


def _cancel_incomplete_tool_calls(db: Session, run: AgentRun) -> list[AgentRunEvent]:
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
            _persist_run_event(
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


def _record_reasoning_update_event(
    db: Session,
    *,
    run: AgentRun,
    message: str,
    source: AgentRunEventSource,
) -> AgentRunEvent | None:
    normalized_message = _normalize_reasoning_message(message)
    if normalized_message is None:
        return None
    return _persist_run_event(
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


def _extract_reasoning_from_tool_result(
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
    return None, _reasoning_source_from_value(output_json.get("source") or arguments.get("source"))


def _tool_result_llm_message(prepared_tool_call: PreparedToolCall, result: ToolExecutionResult) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": prepared_tool_call.tool_call.get("id"),
        "name": prepared_tool_call.tool_name,
        "content": result.output_text,
    }


def _ensure_run_started_event(db: Session, run: AgentRun) -> AgentRunEvent | None:
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
    return _persist_run_event(db, run=run, event_type=AgentRunEventType.RUN_STARTED)


def _run_has_terminal_event(db: Session, run_id: str) -> bool:
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


def _coerce_usage_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _extract_usage(response_message: dict[str, Any]) -> dict[str, int | None]:
    usage = response_message.get("usage")
    if not isinstance(usage, dict):
        return {field: None for field in USAGE_FIELDS}
    return {field: _coerce_usage_int(usage.get(field)) for field in USAGE_FIELDS}


def _accumulate_usage_totals(
    totals: dict[str, int | None],
    usage: dict[str, int | None],
) -> None:
    for field in USAGE_FIELDS:
        value = usage.get(field)
        if value is None:
            continue
        current = totals[field]
        totals[field] = value if current is None else current + value


def _apply_usage_totals_to_run(run: AgentRun, totals: dict[str, int | None]) -> None:
    run.input_tokens = totals["input_tokens"]
    run.output_tokens = totals["output_tokens"]
    run.cache_read_tokens = totals["cache_read_tokens"]
    run.cache_write_tokens = totals["cache_write_tokens"]


def _calculate_context_tokens(
    *,
    model_name: str,
    llm_messages: list[dict[str, Any]],
) -> int | None:
    return count_context_tokens(
        model_name=model_name,
        messages=llm_messages,
        tools=build_openai_tool_schemas(),
    )


def _update_run_context_tokens(
    *,
    run: AgentRun,
    llm_messages: list[dict[str, Any]],
) -> None:
    run.context_tokens = _calculate_context_tokens(
        model_name=run.model_name,
        llm_messages=llm_messages,
    )


def _final_assistant_content(content: str) -> str:
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


def _create_run(
    db: Session,
    *,
    thread: AgentThread,
    user_message: AgentMessage,
) -> AgentRun:
    settings = resolve_runtime_settings(db)
    llm_messages = build_llm_messages(db, thread.id, current_user_message_id=user_message.id)

    run = AgentRun(
        thread_id=thread.id,
        user_message_id=user_message.id,
        status=AgentRunStatus.RUNNING,
        model_name=settings.agent_model,
        context_tokens=_calculate_context_tokens(
            model_name=settings.agent_model,
            llm_messages=llm_messages,
        ),
    )
    thread.updated_at = utc_now()
    db.add(run)
    db.add(thread)
    db.commit()
    db.refresh(run)
    return run


def _run_is_stopped(db: Session, run: AgentRun) -> bool:
    db.refresh(run, attribute_names=["status"])
    return run.status != AgentRunStatus.RUNNING


def _events_after_sequence(db: Session, run_id: str, sequence_index: int) -> list[AgentRunEvent]:
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


def _persist_terminal_run_state(
    db: Session,
    *,
    thread: AgentThread | None,
    run: AgentRun,
    status: AgentRunStatus,
    error_text: str | None,
    event_type: AgentRunEventType,
    event_message: str | None,
    assistant_content: str | None = None,
    persist_assistant_message: bool = True,
) -> AgentRunEvent | None:
    if _run_has_terminal_event(db, run.id):
        return None

    if persist_assistant_message and assistant_content is not None:
        _persist_final_message(
            db,
            thread if thread is not None else db.get(AgentThread, run.thread_id),  # pragma: no cover - defensive
            run,
            assistant_content,
            status=status,
            error_text=error_text,
            commit=False,
        )
    else:
        run.status = status
        run.error_text = error_text
        run.completed_at = utc_now()
        if thread is not None:
            thread.updated_at = utc_now()
            db.add(thread)
        db.add(run)
        db.flush()

    terminal_event = _persist_run_event(
        db,
        run=run,
        event_type=event_type,
        message=event_message,
    )
    db.commit()
    return terminal_event


def _prepare_tool_turn(
    db: Session,
    *,
    run: AgentRun,
    llm_messages: list[dict[str, Any]],
    assistant_content: str,
    model_reasoning: str,
    tool_calls: list[dict[str, Any]],
) -> tuple[list[PreparedToolCall], list[AgentRunEvent]]:
    prepared_calls: list[PreparedToolCall] = []
    event_rows: list[AgentRunEvent] = []

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
            "tool_calls": tool_calls,
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

    for tool_call in tool_calls:
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

    _update_run_context_tokens(run=run, llm_messages=llm_messages)
    db.add(run)
    db.commit()
    return prepared_calls, event_rows


def _run_prepared_tool_call_nonstream(
    db: Session,
    *,
    run: AgentRun,
    prepared_tool_call: PreparedToolCall,
    tool_context: ToolContext,
    llm_messages: list[dict[str, Any]],
) -> None:
    if prepared_tool_call.tool_name == INTERMEDIATE_UPDATE_TOOL_NAME:
        result = execute_tool(prepared_tool_call.tool_name, prepared_tool_call.arguments, tool_context)
        llm_messages.append(_tool_result_llm_message(prepared_tool_call, result))
        reasoning_message, source = _extract_reasoning_from_tool_result(result, prepared_tool_call.arguments)
        _record_reasoning_update_event(
            db,
            run=run,
            message=reasoning_message or "",
            source=source,
        )
        _update_run_context_tokens(run=run, llm_messages=llm_messages)
        db.add(run)
        db.commit()
        return

    tool_row = prepared_tool_call.persisted_row
    if tool_row is None:  # pragma: no cover - defensive guard
        return

    _mark_tool_call_running(db, tool_row)
    _persist_run_event(
        db,
        run=run,
        event_type=AgentRunEventType.TOOL_CALL_STARTED,
        tool_call=tool_row,
    )
    db.commit()

    result = execute_tool(prepared_tool_call.tool_name, prepared_tool_call.arguments, tool_context)
    db.refresh(tool_row, attribute_names=["status"])
    if tool_row.status == AgentToolCallStatus.CANCELLED:
        return

    if result.status == "ok":
        _finalize_tool_call_success(db, tool_call=tool_row, result=result)
        terminal_type = AgentRunEventType.TOOL_CALL_COMPLETED
    else:
        _finalize_tool_call_error(db, tool_call=tool_row, result=result)
        terminal_type = AgentRunEventType.TOOL_CALL_FAILED
    _persist_run_event(db, run=run, event_type=terminal_type, tool_call=tool_row)
    llm_messages.append(_tool_result_llm_message(prepared_tool_call, result))
    _update_run_context_tokens(run=run, llm_messages=llm_messages)
    db.add(run)
    db.commit()


def _execute_agent_run(
    db: Session,
    *,
    thread: AgentThread,
    run: AgentRun,
) -> AgentRun:
    settings = resolve_runtime_settings(db)
    max_steps = max(settings.agent_max_steps, 1)

    started_event = _ensure_run_started_event(db, run)
    if started_event is not None:
        db.commit()

    llm_messages = build_llm_messages(db, thread.id, current_user_message_id=run.user_message_id)
    tool_context = ToolContext(db=db, run_id=run.id)
    run_count = db.scalar(select(func.count(AgentRun.id)).where(AgentRun.thread_id == thread.id)) or 0
    is_first_run_in_thread = run_count == 1
    run_index = run_count
    usage_totals: dict[str, int | None] = {
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cache_read_tokens": run.cache_read_tokens,
        "cache_write_tokens": run.cache_write_tokens,
    }

    try:
        for step_index in range(max_steps):
            if _run_is_stopped(db, run):
                return _load_run_snapshot(db, run.id)

            observability = _model_observability_context(
                current_user_name=settings.current_user_name,
                thread_id=thread.id,
                run_id=run.id,
                step=step_index + 1,
                is_first_run_in_thread=is_first_run_in_thread,
                run_index=run_index,
            )
            assistant_message = _call_model(
                llm_messages,
                db,
                observability=observability,
            )
            if _run_is_stopped(db, run):
                return _load_run_snapshot(db, run.id)

            _accumulate_usage_totals(usage_totals, _extract_usage(assistant_message))
            _apply_usage_totals_to_run(run, usage_totals)
            db.add(run)

            tool_calls = assistant_message.get("tool_calls") or []
            assistant_content = assistant_message.get("content") or ""
            model_reasoning = (assistant_message.get("reasoning") or "").strip()

            if tool_calls:
                prepared_calls, _event_rows = _prepare_tool_turn(
                    db,
                    run=run,
                    llm_messages=llm_messages,
                    assistant_content=assistant_content,
                    model_reasoning=model_reasoning,
                    tool_calls=tool_calls,
                )
                for prepared_tool_call in prepared_calls:
                    if _run_is_stopped(db, run):
                        return _load_run_snapshot(db, run.id)
                    _run_prepared_tool_call_nonstream(
                        db,
                        run=run,
                        prepared_tool_call=prepared_tool_call,
                        tool_context=tool_context,
                        llm_messages=llm_messages,
                    )
                continue

            reasoning_event = _record_reasoning_update_event(
                db,
                run=run,
                message=model_reasoning,
                source=AgentRunEventSource.MODEL_REASONING,
            )
            if reasoning_event is not None:
                db.commit()

            _persist_terminal_run_state(
                db,
                thread=thread,
                run=run,
                status=AgentRunStatus.COMPLETED,
                error_text=None,
                event_type=AgentRunEventType.RUN_COMPLETED,
                event_message=None,
                assistant_content=_final_assistant_content(assistant_content),
            )
            return _load_run_snapshot(db, run.id)

        _persist_terminal_run_state(
            db,
            thread=thread,
            run=run,
            status=AgentRunStatus.FAILED,
            error_text="maximum tool steps reached",
            event_type=AgentRunEventType.RUN_FAILED,
            event_message="maximum tool steps reached",
            assistant_content=(
                "I reached the configured max tool steps before finishing. "
                "Please review the existing tool outputs and pending review items."
            ),
        )
        return _load_run_snapshot(db, run.id)
    except AgentModelError as exc:
        _persist_terminal_run_state(
            db,
            thread=thread,
            run=run,
            status=AgentRunStatus.FAILED,
            error_text=str(exc),
            event_type=AgentRunEventType.RUN_FAILED,
            event_message=str(exc),
            assistant_content=(
                "I could not complete this run because the language model request failed.\n"
                f"Error: {str(exc)}"
            ),
        )
        return _load_run_snapshot(db, run.id)
    except Exception as exc:  # pragma: no cover - defensive guard
        _persist_terminal_run_state(
            db,
            thread=thread,
            run=run,
            status=AgentRunStatus.FAILED,
            error_text=str(exc),
            event_type=AgentRunEventType.RUN_FAILED,
            event_message=str(exc),
            assistant_content="I encountered an internal error while processing this request.",
        )
        return _load_run_snapshot(db, run.id)


def _execute_agent_run_stream(
    db: Session,
    *,
    thread: AgentThread,
    run: AgentRun,
) -> Iterator[dict[str, Any]]:
    settings = resolve_runtime_settings(db)
    max_steps = max(settings.agent_max_steps, 1)
    last_emitted_sequence = 0

    def emit_row(event_row: AgentRunEvent) -> dict[str, Any]:
        nonlocal last_emitted_sequence
        last_emitted_sequence = max(last_emitted_sequence, event_row.sequence_index)
        return _emit_run_event(run, event_row)

    started_event = _ensure_run_started_event(db, run)
    if started_event is not None:
        db.commit()
        yield emit_row(started_event)

    llm_messages = build_llm_messages(db, thread.id, current_user_message_id=run.user_message_id)
    tool_context = ToolContext(db=db, run_id=run.id)
    run_count = db.scalar(select(func.count(AgentRun.id)).where(AgentRun.thread_id == thread.id)) or 0
    is_first_run_in_thread = run_count == 1
    run_index = run_count
    usage_totals: dict[str, int | None] = {
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cache_read_tokens": run.cache_read_tokens,
        "cache_write_tokens": run.cache_write_tokens,
    }

    try:
        for step_index in range(max_steps):
            if _run_is_stopped(db, run):
                for event_row in _events_after_sequence(db, run.id, last_emitted_sequence):
                    yield emit_row(event_row)
                return

            observability = _model_observability_context(
                current_user_name=settings.current_user_name,
                thread_id=thread.id,
                run_id=run.id,
                step=step_index + 1,
                is_first_run_in_thread=is_first_run_in_thread,
                run_index=run_index,
            )
            assistant_message: dict[str, Any] | None = None
            for event in _call_model_stream(
                llm_messages,
                db,
                observability=observability,
            ):
                event_type = str(event.get("type") or "")
                if event_type == "text_delta":
                    delta = str(event.get("delta") or "")
                    if delta:
                        yield {"type": "text_delta", "run_id": run.id, "delta": delta}
                    continue
                if event_type == "done":
                    maybe_message = event.get("message")
                    if isinstance(maybe_message, dict):
                        assistant_message = maybe_message

            if assistant_message is None:
                raise AgentModelError("model request failed: no response")

            if _run_is_stopped(db, run):
                for event_row in _events_after_sequence(db, run.id, last_emitted_sequence):
                    yield emit_row(event_row)
                return

            _accumulate_usage_totals(usage_totals, _extract_usage(assistant_message))
            _apply_usage_totals_to_run(run, usage_totals)
            db.add(run)

            tool_calls = assistant_message.get("tool_calls") or []
            assistant_content = assistant_message.get("content") or ""
            model_reasoning = (assistant_message.get("reasoning") or "").strip()

            if tool_calls:
                prepared_calls, event_rows = _prepare_tool_turn(
                    db,
                    run=run,
                    llm_messages=llm_messages,
                    assistant_content=assistant_content,
                    model_reasoning=model_reasoning,
                    tool_calls=tool_calls,
                )
                for event_row in event_rows:
                    yield emit_row(event_row)

                for prepared_tool_call in prepared_calls:
                    if _run_is_stopped(db, run):
                        for event_row in _events_after_sequence(db, run.id, last_emitted_sequence):
                            yield emit_row(event_row)
                        return

                    if prepared_tool_call.tool_name == INTERMEDIATE_UPDATE_TOOL_NAME:
                        result = execute_tool(prepared_tool_call.tool_name, prepared_tool_call.arguments, tool_context)
                        llm_messages.append(_tool_result_llm_message(prepared_tool_call, result))
                        reasoning_message, source = _extract_reasoning_from_tool_result(result, prepared_tool_call.arguments)
                        reasoning_event = _record_reasoning_update_event(
                            db,
                            run=run,
                            message=reasoning_message or "",
                            source=source,
                        )
                        _update_run_context_tokens(run=run, llm_messages=llm_messages)
                        db.add(run)
                        db.commit()
                        if reasoning_event is not None:
                            yield emit_row(reasoning_event)
                        continue

                    tool_row = prepared_tool_call.persisted_row
                    if tool_row is None:  # pragma: no cover - defensive guard
                        continue

                    _mark_tool_call_running(db, tool_row)
                    started_row = _persist_run_event(
                        db,
                        run=run,
                        event_type=AgentRunEventType.TOOL_CALL_STARTED,
                        tool_call=tool_row,
                    )
                    db.commit()
                    yield emit_row(started_row)

                    result = execute_tool(prepared_tool_call.tool_name, prepared_tool_call.arguments, tool_context)
                    db.refresh(tool_row, attribute_names=["status"])
                    if tool_row.status == AgentToolCallStatus.CANCELLED:
                        continue

                    if result.status == "ok":
                        _finalize_tool_call_success(db, tool_call=tool_row, result=result)
                        completion_type = AgentRunEventType.TOOL_CALL_COMPLETED
                    else:
                        _finalize_tool_call_error(db, tool_call=tool_row, result=result)
                        completion_type = AgentRunEventType.TOOL_CALL_FAILED
                    completed_row = _persist_run_event(
                        db,
                        run=run,
                        event_type=completion_type,
                        tool_call=tool_row,
                    )
                    llm_messages.append(_tool_result_llm_message(prepared_tool_call, result))
                    _update_run_context_tokens(run=run, llm_messages=llm_messages)
                    db.add(run)
                    db.commit()
                    yield emit_row(completed_row)
                continue

            reasoning_event = _record_reasoning_update_event(
                db,
                run=run,
                message=model_reasoning,
                source=AgentRunEventSource.MODEL_REASONING,
            )
            if reasoning_event is not None:
                db.commit()
                yield emit_row(reasoning_event)

            terminal_event = _persist_terminal_run_state(
                db,
                thread=thread,
                run=run,
                status=AgentRunStatus.COMPLETED,
                error_text=None,
                event_type=AgentRunEventType.RUN_COMPLETED,
                event_message=None,
                assistant_content=_final_assistant_content(assistant_content),
            )
            if terminal_event is not None:
                yield emit_row(terminal_event)
            return

        terminal_event = _persist_terminal_run_state(
            db,
            thread=thread,
            run=run,
            status=AgentRunStatus.FAILED,
            error_text="maximum tool steps reached",
            event_type=AgentRunEventType.RUN_FAILED,
            event_message="maximum tool steps reached",
            assistant_content=(
                "I reached the configured max tool steps before finishing. "
                "Please review the existing tool outputs and pending review items."
            ),
        )
        if terminal_event is not None:
            yield emit_row(terminal_event)
        return
    except AgentModelError as exc:
        terminal_event = _persist_terminal_run_state(
            db,
            thread=thread,
            run=run,
            status=AgentRunStatus.FAILED,
            error_text=str(exc),
            event_type=AgentRunEventType.RUN_FAILED,
            event_message=str(exc),
            assistant_content=(
                "I could not complete this run because the language model request failed.\n"
                f"Error: {str(exc)}"
            ),
        )
        if terminal_event is not None:
            yield emit_row(terminal_event)
        return
    except Exception as exc:  # pragma: no cover - defensive guard
        terminal_event = _persist_terminal_run_state(
            db,
            thread=thread,
            run=run,
            status=AgentRunStatus.FAILED,
            error_text=str(exc),
            event_type=AgentRunEventType.RUN_FAILED,
            event_message=str(exc),
            assistant_content="I encountered an internal error while processing this request.",
        )
        if terminal_event is not None:
            yield emit_row(terminal_event)
        return


def start_agent_run(db: Session, thread: AgentThread, user_message: AgentMessage) -> AgentRun:
    ensure_agent_available(db)
    return _create_run(db, thread=thread, user_message=user_message)


def run_existing_agent_run(db: Session, run_id: str) -> AgentRun | None:
    run = db.get(AgentRun, run_id)
    if run is None:
        return None
    if run.status != AgentRunStatus.RUNNING:
        return _load_run_snapshot(db, run.id)

    thread = db.get(AgentThread, run.thread_id)
    if thread is None:
        _persist_terminal_run_state(
            db,
            thread=None,
            run=run,
            status=AgentRunStatus.FAILED,
            error_text="thread not found",
            event_type=AgentRunEventType.RUN_FAILED,
            event_message="thread not found",
            persist_assistant_message=False,
        )
        return _load_run_snapshot(db, run.id)

    return _execute_agent_run(db, thread=thread, run=run)


def run_existing_agent_run_stream(db: Session, run_id: str) -> Iterator[dict[str, Any]]:
    run = db.get(AgentRun, run_id)
    if run is None:
        return
    if run.status != AgentRunStatus.RUNNING:
        snapshot = _load_run_snapshot(db, run.id)
        for event_row in snapshot.events:
            yield _emit_run_event(snapshot, event_row)
        return

    thread = db.get(AgentThread, run.thread_id)
    if thread is None:
        terminal_event = _persist_terminal_run_state(
            db,
            thread=None,
            run=run,
            status=AgentRunStatus.FAILED,
            error_text="thread not found",
            event_type=AgentRunEventType.RUN_FAILED,
            event_message="thread not found",
            persist_assistant_message=False,
        )
        if terminal_event is not None:
            yield _emit_run_event(run, terminal_event)
        return

    yield from _execute_agent_run_stream(db, thread=thread, run=run)


def run_agent_turn(db: Session, thread: AgentThread, user_message: AgentMessage) -> AgentRun:
    run = start_agent_run(db, thread, user_message)
    return _execute_agent_run(db, thread=thread, run=run)


def interrupt_agent_run(db: Session, run_id: str, *, reason: str = "Run interrupted by user.") -> AgentRun | None:
    run = db.get(AgentRun, run_id)
    if run is None:
        return None
    if run.status != AgentRunStatus.RUNNING:
        return _load_run_snapshot(db, run.id)

    thread = db.get(AgentThread, run.thread_id)
    _cancel_incomplete_tool_calls(db, run)
    _persist_terminal_run_state(
        db,
        thread=thread,
        run=run,
        status=AgentRunStatus.FAILED,
        error_text=reason,
        event_type=AgentRunEventType.RUN_FAILED,
        event_message=reason,
        persist_assistant_message=False,
    )
    return _load_run_snapshot(db, run.id)
