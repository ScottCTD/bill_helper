from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.enums_agent import (
    AgentRunEventSource,
    AgentRunEventType,
    AgentRunStatus,
    AgentToolCallStatus,
)
from backend.models_agent import AgentRun, AgentRunEvent, AgentThread
from backend.services.agent.model_client import AgentModelError
from backend.services.agent.protocol_helpers import tool_call_decode_error_result
from backend.services.agent.run_orchestrator import (
    AgentRunLoopAdapter,
    AssistantStepContext,
    RunLoopOutcome,
)
from backend.services.agent.runtime_state import (
    PreparedToolCall,
    apply_usage_totals_to_run as _apply_usage_totals_to_run,
    ensure_run_started_event as _ensure_run_started_event,
    events_after_sequence as _events_after_sequence,
    extract_reasoning_from_tool_result as _extract_reasoning_from_tool_result,
    finalize_tool_call_error as _finalize_tool_call_error,
    finalize_tool_call_success as _finalize_tool_call_success,
    mark_tool_call_running as _mark_tool_call_running,
    persist_run_event as _persist_run_event,
    record_reasoning_update_event as _record_reasoning_update_event,
    tool_result_llm_message as _tool_result_llm_message,
)
from backend.services.agent.serializers import stream_run_event_to_payload
from backend.services.agent.tool_args import INTERMEDIATE_UPDATE_TOOL_NAME
from backend.services.agent.tool_runtime import execute_tool
from backend.services.agent.tool_types import ToolContext, ToolExecutionStatus
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.users import find_user_by_name


ModelCall = Callable[[list[dict[str, Any]], Session, str | None], dict[str, Any]]
ModelStreamCall = Callable[[list[dict[str, Any]], Session, str | None], Iterator[dict[str, Any]]]
RunContextUpdate = Callable[[AgentRun, list[dict[str, Any]]], None]
RunStoppedCheck = Callable[[Session, AgentRun], bool]
PrepareToolTurn = Callable[
    [Session, AgentRun, list[dict[str, Any]], str, str, list[dict[str, Any]]],
    tuple[list[PreparedToolCall], list[AgentRunEvent]],
]
PersistTerminalState = Callable[..., AgentRunEvent | None]
FinalizeAssistantContent = Callable[[str], str]


def _empty_model_result(
    result: dict[str, Any],
) -> Generator[dict[str, Any], None, dict[str, Any]]:
    if False:  # pragma: no cover - generator shape helper
        yield {}
    return result


@dataclass(slots=True)
class RuntimeLoopDependencies:
    call_model: ModelCall
    call_model_stream: ModelStreamCall
    run_is_stopped: RunStoppedCheck
    prepare_tool_turn: PrepareToolTurn
    persist_terminal_run_state: PersistTerminalState
    update_run_context_tokens: RunContextUpdate
    finalize_assistant_content: FinalizeAssistantContent


class RuntimeRunLoopAdapterBase(AgentRunLoopAdapter[PreparedToolCall]):
    def __init__(
        self,
        *,
        db: Session,
        thread: AgentThread,
        run: AgentRun,
        dependencies: RuntimeLoopDependencies,
    ) -> None:
        self.db = db
        self.thread = thread
        self.run = run
        self.dependencies = dependencies
        self.settings = resolve_runtime_settings(db)
        self._max_steps = max(self.settings.agent_max_steps, 1)
        principal_user = find_user_by_name(db, self.settings.current_user_name)
        self.tool_context = ToolContext(
            db=db,
            run_id=run.id,
            principal_name=self.settings.current_user_name,
            principal_user_id=principal_user.id if principal_user is not None else None,
        )

    @property
    def max_steps(self) -> int:
        return self._max_steps

    def _event_payload(self, event_row: AgentRunEvent) -> dict[str, Any] | None:
        return stream_run_event_to_payload(self.run, event_row)

    def _event_payloads(self, event_rows: list[AgentRunEvent]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for event_row in event_rows:
            payload = self._event_payload(event_row)
            if payload is not None:
                payloads.append(payload)
        return payloads

    def build_initial_messages(self) -> list[dict[str, Any]]:
        from backend.services.agent.message_history import build_llm_messages

        return build_llm_messages(
            self.db,
            self.thread.id,
            current_user_message_id=self.run.user_message_id,
            model_name=self.run.model_name,
            surface=self.run.surface,
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
        return self.dependencies.run_is_stopped(self.db, self.run)

    def prepare_tool_calls(
        self,
        *,
        step: AssistantStepContext,
        llm_messages: list[dict[str, Any]],
    ) -> tuple[list[PreparedToolCall], list[dict[str, Any]]]:
        prepared_calls, event_rows = self.dependencies.prepare_tool_turn(
            self.db,
            self.run,
            llm_messages,
            step.assistant_content,
            step.model_reasoning,
            step.tool_calls,
        )
        return prepared_calls, self._event_payloads(event_rows)

    def execute_prepared_tool_call(
        self,
        *,
        step: AssistantStepContext,
        prepared_tool_call: PreparedToolCall,
        llm_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        decode_error_result = (
            tool_call_decode_error_result(
                tool_name=prepared_tool_call.tool_name,
                raw_arguments=prepared_tool_call.raw_arguments,
                decode_error=prepared_tool_call.decode_error,
            )
            if prepared_tool_call.decode_error is not None
            else None
        )
        if prepared_tool_call.tool_name == INTERMEDIATE_UPDATE_TOOL_NAME:
            result = decode_error_result or execute_tool(
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
            self.dependencies.update_run_context_tokens(self.run, llm_messages)
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

        result = decode_error_result or execute_tool(
            prepared_tool_call.tool_name,
            prepared_tool_call.arguments,
            self.tool_context,
        )
        self.db.refresh(tool_row, attribute_names=["status"])
        if tool_row.status == AgentToolCallStatus.CANCELLED:
            return payloads

        if result.status == ToolExecutionStatus.OK:
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
        self.dependencies.update_run_context_tokens(self.run, llm_messages)
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
        terminal_event = self.dependencies.persist_terminal_run_state(
            self.db,
            thread=self.thread,
            run=self.run,
            status=AgentRunStatus.COMPLETED,
            error_text=None,
            event_type=AgentRunEventType.RUN_COMPLETED,
            event_message=None,
            assistant_content=self.dependencies.finalize_assistant_content(step.assistant_content),
        )
        if terminal_event is None:
            return []
        return self._event_payloads([terminal_event])

    def fail_max_steps(self) -> list[dict[str, Any]]:
        terminal_event = self.dependencies.persist_terminal_run_state(
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
        terminal_event = self.dependencies.persist_terminal_run_state(
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
        terminal_event = self.dependencies.persist_terminal_run_state(
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


class RuntimeNonStreamRunLoopAdapter(RuntimeRunLoopAdapterBase):
    def call_model_step(
        self,
        *,
        step_index: int,
        llm_messages: list[dict[str, Any]],
    ) -> Generator[dict[str, Any], None, dict[str, Any]]:
        assistant_message = self.dependencies.call_model(
            llm_messages,
            self.db,
            model_name=self.run.model_name,
        )
        return (yield from _empty_model_result(assistant_message))


class RuntimeStreamRunLoopAdapter(RuntimeRunLoopAdapterBase):
    def __init__(
        self,
        *,
        db: Session,
        thread: AgentThread,
        run: AgentRun,
        dependencies: RuntimeLoopDependencies,
    ) -> None:
        super().__init__(db=db, thread=thread, run=run, dependencies=dependencies)
        self._last_emitted_sequence = 0

    def _event_payload(self, event_row: AgentRunEvent) -> dict[str, Any] | None:
        self._last_emitted_sequence = max(
            self._last_emitted_sequence,
            event_row.sequence_index,
        )
        return stream_run_event_to_payload(self.run, event_row)

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
        for event in self.dependencies.call_model_stream(
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


def iter_run_loop_payloads(
    loop: Generator[dict[str, Any], None, RunLoopOutcome],
) -> Iterator[dict[str, Any]]:
    try:
        while True:
            yield next(loop)
    except StopIteration:
        return
