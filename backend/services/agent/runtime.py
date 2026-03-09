from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.config import DEFAULT_AGENT_MODEL
from backend.enums_agent import (
    AgentRunEventSource,
    AgentRunEventType,
    AgentRunStatus,
)
from backend.models_agent import (
    AgentMessage,
    AgentRun,
    AgentRunEvent,
    AgentThread,
)
from backend.services.agent.context_tokens import count_context_tokens
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.model_client import (
    LiteLLMModelClient,
    validate_litellm_environment,
)
from backend.services.agent.protocol_helpers import (
    canonicalize_tool_call,
)
from backend.services.agent.runtime_loop import (
    RuntimeLoopDependencies,
    RuntimeNonStreamRunLoopAdapter,
    RuntimeStreamRunLoopAdapter,
    iter_run_loop_payloads,
)
from backend.services.agent.runtime_state import (
    PreparedToolCall,
    cancel_incomplete_tool_calls as _cancel_incomplete_tool_calls,
    load_run_snapshot as _load_run_snapshot,
    persist_final_message as _persist_final_message,
    persist_run_event as _persist_run_event,
    queue_tool_call_record as _queue_tool_call_record,
    record_reasoning_update_event as _record_reasoning_update_event,
    run_has_terminal_event as _run_has_terminal_event,
    utc_now,
)
from backend.services.agent.run_orchestrator import (
    run_agent_loop,
)
from backend.services.agent.tool_runtime import build_openai_tool_schemas
from backend.services.runtime_settings import resolve_runtime_settings
from backend.validation.runtime_settings import normalize_text_or_none


EMPTY_PENDING_REVIEW_FOOTER_PATTERN = re.compile(
    r"^\s*Tools used \(high level\):.*Pending review item ids:\s*\[\s*\]\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class AgentRuntimeUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class ExistingRunResolution:
    state: str
    run: AgentRun | None = None
    thread: AgentThread | None = None
    terminal_event: AgentRunEvent | None = None


def ensure_agent_available(db: Session, *, model_name: str | None = None) -> None:
    settings = resolve_runtime_settings(db)
    requested_model_name = normalize_text_or_none(model_name) or settings.agent_model
    # If custom base_url or api_key is configured, skip LiteLLM env validation
    if settings.agent_base_url or settings.agent_api_key:
        return
    has_credentials, missing_keys, request_model = validate_litellm_environment(
        model_name=requested_model_name,
    )
    if has_credentials:
        return
    missing_text = f" Missing keys: {', '.join(missing_keys)}." if missing_keys else ""
    raise AgentRuntimeUnavailable(
        "Agent runtime is not configured. "
        f"Model target: {request_model}.{missing_text} "
        "Provide provider credentials via environment variables or configure custom base_url and api_key in settings."
    )


def _build_model_client(db: Session, *, model_name: str | None = None) -> LiteLLMModelClient:
    settings = resolve_runtime_settings(db)
    selected_model_name = normalize_text_or_none(model_name) or settings.agent_model or DEFAULT_AGENT_MODEL
    return LiteLLMModelClient(
        model_name=selected_model_name,
        tools=build_openai_tool_schemas(),
        retry_max_attempts=settings.agent_retry_max_attempts,
        retry_initial_wait_seconds=settings.agent_retry_initial_wait_seconds,
        retry_max_wait_seconds=settings.agent_retry_max_wait_seconds,
        retry_backoff_multiplier=settings.agent_retry_backoff_multiplier,
        base_url=settings.agent_base_url,
        api_key=settings.agent_api_key,
    )


def call_model(
    messages: list[dict[str, Any]],
    db: Session,
    *,
    model_name: str | None = None,
) -> dict[str, Any]:
    # Stable seam for tests/bench harnesses to inject model responses.
    return _build_model_client(db, model_name=model_name).complete(messages)


def call_model_stream(
    messages: list[dict[str, Any]],
    db: Session,
    *,
    model_name: str | None = None,
) -> Iterator[dict[str, Any]]:
    # Stable seam for tests/bench harnesses to inject streaming model responses.
    return _build_model_client(db, model_name=model_name).complete_stream(messages)


def calculate_context_tokens(
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
    run.context_tokens = calculate_context_tokens(
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
    model_name: str | None = None,
    surface: str = "app",
) -> AgentRun:
    settings = resolve_runtime_settings(db)
    selected_model_name = normalize_text_or_none(model_name) or settings.agent_model
    llm_messages = build_llm_messages(
        db,
        thread.id,
        current_user_message_id=user_message.id,
        model_name=selected_model_name,
        surface=surface,
    )

    run = AgentRun(
        thread_id=thread.id,
        user_message_id=user_message.id,
        status=AgentRunStatus.RUNNING,
        model_name=selected_model_name,
        surface=surface,
        context_tokens=calculate_context_tokens(
            model_name=selected_model_name,
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
            thread
            if thread is not None
            else db.get(AgentThread, run.thread_id),  # pragma: no cover - defensive
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

    _update_run_context_tokens(run=run, llm_messages=llm_messages)
    db.add(run)
    db.commit()
    return prepared_calls, event_rows


def _runtime_loop_dependencies() -> RuntimeLoopDependencies:
    return RuntimeLoopDependencies(
        call_model=call_model,
        call_model_stream=call_model_stream,
        run_is_stopped=_run_is_stopped,
        prepare_tool_turn=lambda db, run, llm_messages, assistant_content, model_reasoning, tool_calls: _prepare_tool_turn(
            db,
            run=run,
            llm_messages=llm_messages,
            assistant_content=assistant_content,
            model_reasoning=model_reasoning,
            tool_calls=tool_calls,
        ),
        persist_terminal_run_state=_persist_terminal_run_state,
        update_run_context_tokens=lambda run, llm_messages: _update_run_context_tokens(
            run=run,
            llm_messages=llm_messages,
        ),
        finalize_assistant_content=_final_assistant_content,
    )


def _execute_agent_run(
    db: Session,
    *,
    thread: AgentThread,
    run: AgentRun,
) -> AgentRun:
    adapter = RuntimeNonStreamRunLoopAdapter(
        db=db,
        thread=thread,
        run=run,
        dependencies=_runtime_loop_dependencies(),
    )
    for _ in iter_run_loop_payloads(run_agent_loop(adapter)):
        pass
    return _load_run_snapshot(db, run.id)


def _execute_agent_run_stream(
    db: Session,
    *,
    thread: AgentThread,
    run: AgentRun,
) -> Iterator[dict[str, Any]]:
    adapter = RuntimeStreamRunLoopAdapter(
        db=db,
        thread=thread,
        run=run,
        dependencies=_runtime_loop_dependencies(),
    )
    yield from iter_run_loop_payloads(run_agent_loop(adapter))


def _resolve_existing_run(db: Session, run_id: str) -> ExistingRunResolution:
    run = db.get(AgentRun, run_id)
    if run is None:
        return ExistingRunResolution(state="missing")

    if run.status != AgentRunStatus.RUNNING:
        return ExistingRunResolution(
            state="replay",
            run=_load_run_snapshot(db, run.id),
        )

    thread = db.get(AgentThread, run.thread_id)
    if thread is not None:
        return ExistingRunResolution(
            state="execute",
            run=run,
            thread=thread,
        )

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
    return ExistingRunResolution(
        state="failed_missing_thread",
        run=_load_run_snapshot(db, run.id),
        terminal_event=terminal_event,
    )


def start_agent_run(
    db: Session,
    thread: AgentThread,
    user_message: AgentMessage,
    *,
    model_name: str | None = None,
    surface: str = "app",
) -> AgentRun:
    ensure_agent_available(db, model_name=model_name)
    return _create_run(
        db,
        thread=thread,
        user_message=user_message,
        model_name=model_name,
        surface=surface,
    )


def run_existing_agent_run(db: Session, run_id: str) -> AgentRun | None:
    resolution = _resolve_existing_run(db, run_id)
    if resolution.state == "missing":
        return None
    if resolution.state in {"replay", "failed_missing_thread"}:
        return resolution.run
    if resolution.run is None or resolution.thread is None:  # pragma: no cover - defensive
        return None
    return _execute_agent_run(db, thread=resolution.thread, run=resolution.run)


def run_existing_agent_run_stream(db: Session, run_id: str) -> Iterator[dict[str, Any]]:
    resolution = _resolve_existing_run(db, run_id)
    if resolution.state == "missing":
        return
    if resolution.state == "replay":
        if resolution.run is None:
            return
        for event_row in resolution.run.events:
            yield stream_run_event_to_payload(resolution.run, event_row)
        return
    if resolution.state == "failed_missing_thread":
        if resolution.run is None or resolution.terminal_event is None:
            return
        yield stream_run_event_to_payload(resolution.run, resolution.terminal_event)
        return

    if resolution.run is None or resolution.thread is None:  # pragma: no cover - defensive
        return
    yield from _execute_agent_run_stream(
        db,
        thread=resolution.thread,
        run=resolution.run,
    )


def run_agent_turn(
    db: Session, thread: AgentThread, user_message: AgentMessage
) -> AgentRun:
    run = start_agent_run(db, thread, user_message)
    return _execute_agent_run(db, thread=thread, run=run)


def interrupt_agent_run(
    db: Session, run_id: str, *, reason: str = "Run interrupted by user."
) -> AgentRun | None:
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
