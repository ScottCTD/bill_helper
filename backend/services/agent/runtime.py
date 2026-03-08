from __future__ import annotations

from collections.abc import Generator, Iterator
from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.config import DEFAULT_AGENT_MODEL
from backend.enums_agent import (
    AgentRunEventSource,
    AgentRunEventType,
    AgentRunStatus,
    AgentToolCallStatus,
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
    AgentModelError,
    LiteLLMModelClient,
    validate_litellm_environment,
)
from backend.services.agent.protocol_helpers import canonicalize_tool_call
from backend.services.agent.runtime_state import (
    PreparedToolCall,
    apply_usage_totals_to_run as _apply_usage_totals_to_run,
    cancel_incomplete_tool_calls as _cancel_incomplete_tool_calls,
    emit_run_event as _emit_run_event,
    ensure_run_started_event as _ensure_run_started_event,
    events_after_sequence as _events_after_sequence,
    extract_reasoning_from_tool_result as _extract_reasoning_from_tool_result,
    finalize_tool_call_error as _finalize_tool_call_error,
    finalize_tool_call_success as _finalize_tool_call_success,
    load_run_snapshot as _load_run_snapshot,
    mark_tool_call_running as _mark_tool_call_running,
    persist_final_message as _persist_final_message,
    persist_run_event as _persist_run_event,
    queue_tool_call_record as _queue_tool_call_record,
    record_reasoning_update_event as _record_reasoning_update_event,
    run_has_terminal_event as _run_has_terminal_event,
    tool_result_llm_message as _tool_result_llm_message,
    utc_now,
)
from backend.services.agent.run_orchestrator import (
    AgentRunLoopAdapter,
    AssistantStepContext,
    RunLoopOutcome,
    run_agent_loop,
)
from backend.services.agent.tools import (
    INTERMEDIATE_UPDATE_TOOL_NAME,
    ToolContext,
    build_openai_tool_schemas,
    execute_tool,
)
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.runtime_settings_normalization import normalize_text_or_none


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
) -> AgentRun:
    settings = resolve_runtime_settings(db)
    selected_model_name = normalize_text_or_none(model_name) or settings.agent_model
    llm_messages = build_llm_messages(
        db,
        thread.id,
        current_user_message_id=user_message.id,
        model_name=selected_model_name,
    )

    run = AgentRun(
        thread_id=thread.id,
        user_message_id=user_message.id,
        status=AgentRunStatus.RUNNING,
        model_name=selected_model_name,
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


def _empty_model_result(
    result: dict[str, Any],
) -> Generator[dict[str, Any], None, dict[str, Any]]:
    if False:  # pragma: no cover - generator shape helper
        yield {}
    return result


class _RuntimeRunLoopAdapterBase(AgentRunLoopAdapter[PreparedToolCall]):
    def __init__(
        self,
        *,
        db: Session,
        thread: AgentThread,
        run: AgentRun,
    ) -> None:
        self.db = db
        self.thread = thread
        self.run = run
        self.settings = resolve_runtime_settings(db)
        self._max_steps = max(self.settings.agent_max_steps, 1)
        self.tool_context = ToolContext(db=db, run_id=run.id)

    @property
    def max_steps(self) -> int:
        return self._max_steps

    def _event_payload(self, event_row: AgentRunEvent) -> dict[str, Any] | None:
        return _emit_run_event(self.run, event_row)

    def _event_payloads(self, event_rows: list[AgentRunEvent]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for event_row in event_rows:
            payload = self._event_payload(event_row)
            if payload is not None:
                payloads.append(payload)
        return payloads

    def build_initial_messages(self) -> list[dict[str, Any]]:
        return build_llm_messages(
            self.db,
            self.thread.id,
            current_user_message_id=self.run.user_message_id,
            model_name=self.run.model_name,
        )

    def initial_usage_totals(self) -> dict[str, int | None]:
        return {
            "input_tokens": self.run.input_tokens,
            "output_tokens": self.run.output_tokens,
            "cache_read_tokens": self.run.cache_read_tokens,
            "cache_write_tokens": self.run.cache_write_tokens,
        }

    def apply_usage_totals(self, usage_totals: dict[str, int | None]) -> None:
        _apply_usage_totals_to_run(self.run, usage_totals)
        self.db.add(self.run)

    def on_loop_started(self) -> list[dict[str, Any]]:
        started_event = _ensure_run_started_event(self.db, self.run)
        if started_event is None:
            return []
        self.db.commit()
        return self._event_payloads([started_event])

    def is_stopped(self) -> bool:
        return _run_is_stopped(self.db, self.run)

    def prepare_tool_calls(
        self,
        *,
        step: AssistantStepContext,
        llm_messages: list[dict[str, Any]],
    ) -> tuple[list[PreparedToolCall], list[dict[str, Any]]]:
        prepared_calls, event_rows = _prepare_tool_turn(
            self.db,
            run=self.run,
            llm_messages=llm_messages,
            assistant_content=step.assistant_content,
            model_reasoning=step.model_reasoning,
            tool_calls=step.tool_calls,
        )
        return prepared_calls, self._event_payloads(event_rows)

    def execute_prepared_tool_call(
        self,
        *,
        step: AssistantStepContext,
        prepared_tool_call: PreparedToolCall,
        llm_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if prepared_tool_call.tool_name == INTERMEDIATE_UPDATE_TOOL_NAME:
            result = execute_tool(
                prepared_tool_call.tool_name,
                prepared_tool_call.arguments,
                self.tool_context,
            )
            llm_messages.append(_tool_result_llm_message(prepared_tool_call, result))
            reasoning_message, source = _extract_reasoning_from_tool_result(
                result,
                prepared_tool_call.arguments,
            )
            reasoning_event = _record_reasoning_update_event(
                self.db,
                run=self.run,
                message=reasoning_message or "",
                source=source,
            )
            _update_run_context_tokens(run=self.run, llm_messages=llm_messages)
            self.db.add(self.run)
            self.db.commit()
            return self._event_payloads([reasoning_event] if reasoning_event is not None else [])

        tool_row = prepared_tool_call.persisted_row
        if tool_row is None:  # pragma: no cover - defensive guard
            return []

        _mark_tool_call_running(self.db, tool_row)
        started_row = _persist_run_event(
            self.db,
            run=self.run,
            event_type=AgentRunEventType.TOOL_CALL_STARTED,
            tool_call=tool_row,
        )
        self.db.commit()
        payloads = self._event_payloads([started_row])

        result = execute_tool(
            prepared_tool_call.tool_name,
            prepared_tool_call.arguments,
            self.tool_context,
        )
        self.db.refresh(tool_row, attribute_names=["status"])
        if tool_row.status == AgentToolCallStatus.CANCELLED:
            return payloads

        if result.status == "ok":
            _finalize_tool_call_success(self.db, tool_call=tool_row, result=result)
            completion_type = AgentRunEventType.TOOL_CALL_COMPLETED
        else:
            _finalize_tool_call_error(self.db, tool_call=tool_row, result=result)
            completion_type = AgentRunEventType.TOOL_CALL_FAILED

        completed_row = _persist_run_event(
            self.db,
            run=self.run,
            event_type=completion_type,
            tool_call=tool_row,
        )
        llm_messages.append(_tool_result_llm_message(prepared_tool_call, result))
        _update_run_context_tokens(run=self.run, llm_messages=llm_messages)
        self.db.add(self.run)
        self.db.commit()
        payloads.extend(self._event_payloads([completed_row]))
        return payloads

    def record_model_reasoning(self, *, step: AssistantStepContext) -> list[dict[str, Any]]:
        reasoning_event = _record_reasoning_update_event(
            self.db,
            run=self.run,
            message=step.model_reasoning,
            source=AgentRunEventSource.MODEL_REASONING,
        )
        if reasoning_event is None:
            return []
        self.db.commit()
        return self._event_payloads([reasoning_event])

    def complete(self, *, step: AssistantStepContext) -> list[dict[str, Any]]:
        terminal_event = _persist_terminal_run_state(
            self.db,
            thread=self.thread,
            run=self.run,
            status=AgentRunStatus.COMPLETED,
            error_text=None,
            event_type=AgentRunEventType.RUN_COMPLETED,
            event_message=None,
            assistant_content=_final_assistant_content(step.assistant_content),
        )
        if terminal_event is None:
            return []
        return self._event_payloads([terminal_event])

    def fail_max_steps(self) -> list[dict[str, Any]]:
        terminal_event = _persist_terminal_run_state(
            self.db,
            thread=self.thread,
            run=self.run,
            status=AgentRunStatus.FAILED,
            error_text="maximum tool steps reached",
            event_type=AgentRunEventType.RUN_FAILED,
            event_message="maximum tool steps reached",
            assistant_content=(
                "I reached the configured max tool steps before finishing. "
                "Please review the existing tool outputs and pending review items."
            ),
        )
        if terminal_event is None:
            return []
        return self._event_payloads([terminal_event])

    def fail_model_error(self, error: AgentModelError) -> list[dict[str, Any]]:
        terminal_event = _persist_terminal_run_state(
            self.db,
            thread=self.thread,
            run=self.run,
            status=AgentRunStatus.FAILED,
            error_text=str(error),
            event_type=AgentRunEventType.RUN_FAILED,
            event_message=str(error),
            assistant_content=(
                "I could not complete this run because the language model request failed.\n"
                f"Error: {str(error)}"
            ),
        )
        if terminal_event is None:
            return []
        return self._event_payloads([terminal_event])

    def fail_unexpected_error(self, error: Exception) -> list[dict[str, Any]]:
        terminal_event = _persist_terminal_run_state(
            self.db,
            thread=self.thread,
            run=self.run,
            status=AgentRunStatus.FAILED,
            error_text=str(error),
            event_type=AgentRunEventType.RUN_FAILED,
            event_message=str(error),
            assistant_content="I encountered an internal error while processing this request.",
        )
        if terminal_event is None:
            return []
        return self._event_payloads([terminal_event])


class _RuntimeNonStreamRunLoopAdapter(_RuntimeRunLoopAdapterBase):
    def call_model_step(
        self,
        *,
        step_index: int,
        llm_messages: list[dict[str, Any]],
    ) -> Generator[dict[str, Any], None, dict[str, Any]]:
        assistant_message = call_model(
            llm_messages,
            self.db,
            model_name=self.run.model_name,
        )
        return (yield from _empty_model_result(assistant_message))


class _RuntimeStreamRunLoopAdapter(_RuntimeRunLoopAdapterBase):
    def __init__(
        self,
        *,
        db: Session,
        thread: AgentThread,
        run: AgentRun,
    ) -> None:
        super().__init__(db=db, thread=thread, run=run)
        self._last_emitted_sequence = 0

    def _event_payload(self, event_row: AgentRunEvent) -> dict[str, Any] | None:
        self._last_emitted_sequence = max(
            self._last_emitted_sequence,
            event_row.sequence_index,
        )
        return _emit_run_event(self.run, event_row)

    def on_stopped(self) -> list[dict[str, Any]]:
        return self._event_payloads(
            _events_after_sequence(self.db, self.run.id, self._last_emitted_sequence)
        )

    def call_model_step(
        self,
        *,
        step_index: int,
        llm_messages: list[dict[str, Any]],
    ) -> Generator[dict[str, Any], None, dict[str, Any]]:
        assistant_message: dict[str, Any] | None = None
        for event in call_model_stream(
            llm_messages,
            self.db,
            model_name=self.run.model_name,
        ):
            event_type = str(event.get("type") or "")
            if event_type == "reasoning_delta":
                delta = str(event.get("delta") or "")
                if delta:
                    yield {
                        "type": "reasoning_delta",
                        "run_id": self.run.id,
                        "delta": delta,
                    }
                continue
            if event_type == "text_delta":
                delta = str(event.get("delta") or "")
                if delta:
                    yield {"type": "text_delta", "run_id": self.run.id, "delta": delta}
                continue
            if event_type == "done":
                maybe_message = event.get("message")
                if isinstance(maybe_message, dict):
                    assistant_message = maybe_message

        if assistant_message is None:
            raise AgentModelError("model request failed: no response")
        return assistant_message


def _iter_run_loop_payloads(
    loop: Generator[dict[str, Any], None, RunLoopOutcome],
) -> Iterator[dict[str, Any]]:
    try:
        while True:
            yield next(loop)
    except StopIteration:
        return


def _execute_agent_run(
    db: Session,
    *,
    thread: AgentThread,
    run: AgentRun,
) -> AgentRun:
    adapter = _RuntimeNonStreamRunLoopAdapter(db=db, thread=thread, run=run)
    for _ in _iter_run_loop_payloads(run_agent_loop(adapter)):
        pass
    return _load_run_snapshot(db, run.id)


def _execute_agent_run_stream(
    db: Session,
    *,
    thread: AgentThread,
    run: AgentRun,
) -> Iterator[dict[str, Any]]:
    adapter = _RuntimeStreamRunLoopAdapter(db=db, thread=thread, run=run)
    yield from _iter_run_loop_payloads(run_agent_loop(adapter))


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
) -> AgentRun:
    ensure_agent_available(db, model_name=model_name)
    return _create_run(db, thread=thread, user_message=user_message, model_name=model_name)


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
            yield _emit_run_event(resolution.run, event_row)
        return
    if resolution.state == "failed_missing_thread":
        if resolution.run is None or resolution.terminal_event is None:
            return
        yield _emit_run_event(resolution.run, resolution.terminal_event)
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
