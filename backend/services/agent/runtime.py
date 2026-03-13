# CALLING SPEC:
# - Purpose: implement focused service logic for `runtime`.
# - Inputs: callers that import `backend/services/agent/runtime.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `runtime`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from backend.config import DEFAULT_AGENT_MODEL
from backend.models_agent import AgentMessage, AgentRun, AgentThread
from backend.services.agent.context_tokens import count_context_tokens
from backend.services.agent.model_client import (
    LiteLLMModelClient,
    validate_litellm_environment,
)
from backend.services.agent.runtime_loop import (
    RuntimeLoopDependencies,
    RuntimeNonStreamRunLoopAdapter,
    RuntimeStreamRunLoopAdapter,
    iter_run_loop_payloads,
)
from backend.services.agent.runtime_state import load_run_snapshot as _load_run_snapshot
from backend.services.agent.runtime_support.lifecycle import (
    interrupt_run as _interrupt_run,
)
from backend.services.agent.runtime_support.lifecycle import (
    create_run as _create_run,
)
from backend.services.agent.runtime_support.lifecycle import (
    resolve_existing_run as _resolve_existing_run,
)
from backend.services.agent.runtime_support.lifecycle import (
    run_is_stopped as _run_is_stopped,
)
from backend.services.agent.runtime_support.lifecycle import (
    persist_terminal_run_state as _persist_terminal_run_state,
)
from backend.services.agent.runtime_support.tool_turns import (
    final_assistant_content as _final_assistant_content_support,
)
from backend.services.agent.runtime_support.tool_turns import (
    prepare_tool_turn as _prepare_tool_turn_support,
)
from backend.services.agent.runtime_support.tool_turns import (
    update_run_context_tokens as _update_run_context_tokens_support,
)
from backend.services.agent.run_orchestrator import (
    run_agent_loop,
)
from backend.services.agent.serializers import stream_run_event_to_payload
from backend.services.agent.tool_runtime import build_openai_tool_schemas
from backend.services.runtime_settings import resolve_runtime_settings
from backend.validation.runtime_settings import normalize_text_or_none


class AgentRuntimeUnavailable(RuntimeError):
    pass


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
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    response_format: Any = None,
) -> dict[str, Any]:
    # Stable seam for tests/bench harnesses to inject model responses.
    return _build_model_client(db, model_name=model_name).complete(
        messages,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
    )


def call_model_stream(
    messages: list[dict[str, Any]],
    db: Session,
    *,
    model_name: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    response_format: Any = None,
) -> Iterator[dict[str, Any]]:
    # Stable seam for tests/bench harnesses to inject streaming model responses.
    return _build_model_client(db, model_name=model_name).complete_stream(
        messages,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
    )


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
    run: AgentRun,
    llm_messages: list[dict[str, Any]],
) -> None:
    _update_run_context_tokens_support(
        run=run,
        llm_messages=llm_messages,
        calculate_context_tokens=calculate_context_tokens,
    )


def _runtime_loop_dependencies() -> RuntimeLoopDependencies:
    return RuntimeLoopDependencies(
        call_model=call_model,
        call_model_stream=call_model_stream,
        run_is_stopped=_run_is_stopped,
        prepare_tool_turn=lambda db, run, llm_messages, assistant_content, model_reasoning, tool_calls: _prepare_tool_turn_support(
            db,
            run=run,
            llm_messages=llm_messages,
            assistant_content=assistant_content,
            model_reasoning=model_reasoning,
            tool_calls=tool_calls,
            update_run_context_tokens=_update_run_context_tokens,
        ),
        persist_terminal_run_state=_persist_terminal_run_state,
        update_run_context_tokens=_update_run_context_tokens,
        finalize_assistant_content=_final_assistant_content_support,
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
        calculate_context_tokens=calculate_context_tokens,
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
    return _interrupt_run(db, run_id=run_id, reason=reason)
