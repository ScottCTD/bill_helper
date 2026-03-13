# CALLING SPEC:
# - Purpose: implement focused service logic for `benchmark_interface`.
# - Inputs: callers that import `backend/services/agent/benchmark_interface.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `benchmark_interface`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.enums_agent import AgentMessageRole, AgentRunStatus
from backend.models_agent import AgentMessage, AgentMessageAttachment, AgentRun, AgentThread
from backend.models_finance import User
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.model_client import AgentModelError
from backend.services.agent.principal_scope import load_thread_owner_user
from backend.services.agent.protocol_helpers import (
    USAGE_FIELDS,
    canonicalize_tool_call,
    decode_tool_call,
    extract_usage_dict,
    tool_call_decode_error_result,
)
from backend.services.agent.run_orchestrator import (
    AgentRunLoopAdapter,
    AssistantStepContext,
    ModelStepGenerator,
    RunLoopOutcome,
    run_agent_loop,
)
from backend.services.agent.runtime import call_model
from backend.services.agent.tool_runtime import execute_tool
from backend.services.agent.tool_types import ToolContext
from backend.services.runtime_settings import resolve_runtime_settings

PROPOSAL_TOOL_NAMES = {
    "propose_create_tag",
    "propose_create_entity",
    "propose_create_entry",
}
BENCHMARK_ENTRY_NOTES_KEY = "markdown_notes"


@dataclass(slots=True)
class BenchmarkAttachmentInput:
    file_path: str
    mime_type: str


@dataclass(slots=True)
class BenchmarkTraceStep:
    step: int
    messages_sent: list[dict[str, Any]]
    model_response: dict[str, Any]
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    wall_clock_ms: int = 0


@dataclass(slots=True)
class BenchmarkPredictionSet:
    tags: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    entries: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class BenchmarkCaseExecution:
    run_status: str
    error: str | None
    predictions: BenchmarkPredictionSet
    trace_steps: list[BenchmarkTraceStep]
    total_usage: dict[str, int | None]
    total_wall_clock_ms: int
    final_assistant_content: str


@dataclass(slots=True)
class _PreparedToolCall:
    tool_call: dict[str, Any]
    tool_name: str
    arguments: dict[str, Any]
    raw_arguments: str | None = None
    decode_error: str | None = None


@dataclass(slots=True)
class _BenchmarkRunState:
    trace_steps: list[BenchmarkTraceStep] = field(default_factory=list)
    proposal_inputs: list[dict[str, Any]] = field(default_factory=list)
    final_assistant_content: str = ""
    execution_error: str | None = None


def _redact_image_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    redacted = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    if url.startswith("data:"):
                        media_type = url.split(";")[0] if ";" in url else "data:image/unknown"
                        new_parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": f"{media_type};base64,[REDACTED {len(url)} chars]"},
                            }
                        )
                    else:
                        new_parts.append(part)
                else:
                    new_parts.append(part)
            redacted.append({**msg, "content": new_parts})
        else:
            redacted.append(msg)
    return redacted


def _predictions_from_proposals(proposals: list[dict[str, Any]]) -> BenchmarkPredictionSet:
    predictions = BenchmarkPredictionSet()
    for proposal in proposals:
        tool_name = proposal.get("tool_name")
        arguments = proposal.get("arguments")
        if not isinstance(arguments, dict):
            continue
        if tool_name == "propose_create_tag":
            predictions.tags.append(
                {
                    "name": arguments.get("name"),
                    "type": arguments.get("type"),
                }
            )
        elif tool_name == "propose_create_entity":
            predictions.entities.append(
                {
                    "name": arguments.get("name"),
                    "category": arguments.get("category"),
                }
            )
        elif tool_name == "propose_create_entry":
            entry_prediction = {
                "kind": arguments.get("kind"),
                "date": arguments.get("date"),
                "name": arguments.get("name"),
                "amount_minor": arguments.get("amount_minor"),
                "currency_code": arguments.get("currency_code"),
                "from_entity": arguments.get("from_entity"),
                "to_entity": arguments.get("to_entity"),
                "tags": arguments.get("tags", []),
            }
            entry_prediction[BENCHMARK_ENTRY_NOTES_KEY] = arguments.get("markdown_notes")
            predictions.entries.append(entry_prediction)
    return predictions


def _create_benchmark_run(
    db: Session,
    *,
    text: str,
    attachments: list[BenchmarkAttachmentInput],
    model_name: str,
    owner_user: User,
) -> tuple[AgentThread, AgentMessage, AgentRun]:
    thread = AgentThread(owner_user_id=owner_user.id)
    db.add(thread)
    db.flush()

    user_message = AgentMessage(
        thread_id=thread.id,
        role=AgentMessageRole.USER,
        content_markdown=text,
    )
    db.add(user_message)
    db.flush()

    for attachment in attachments:
        db.add(
            AgentMessageAttachment(
                message_id=user_message.id,
                mime_type=attachment.mime_type,
                file_path=attachment.file_path,
            )
        )
    db.flush()

    run = AgentRun(
        thread_id=thread.id,
        user_message_id=user_message.id,
        status=AgentRunStatus.RUNNING,
        model_name=model_name,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return thread, user_message, run


def _mark_failed_run(
    db: Session,
    run: AgentRun,
    state: _BenchmarkRunState,
    *,
    error_text: str,
) -> None:
    run.status = AgentRunStatus.FAILED
    run.error_text = error_text
    state.execution_error = error_text
    db.add(run)
    db.commit()


def _run_loop_outcome(
    adapter: AgentRunLoopAdapter[_PreparedToolCall],
) -> RunLoopOutcome:
    loop = run_agent_loop(adapter)
    try:
        while True:
            next(loop)
    except StopIteration as done:
        return done.value


class _BenchmarkRunLoopAdapter(AgentRunLoopAdapter[_PreparedToolCall]):
    def __init__(
        self,
        *,
        db: Session,
        run: AgentRun,
        thread_id: str,
        user_message_id: str,
        max_steps: int,
        state: _BenchmarkRunState,
    ) -> None:
        self._db = db
        self._run = run
        self._thread_id = thread_id
        self._user_message_id = user_message_id
        self._max_steps = max_steps
        self._state = state
        owner_user = load_thread_owner_user(db, thread_id=thread_id)
        self._tool_context = ToolContext(
            db=db,
            run_id=run.id,
            principal_name=owner_user.name if owner_user is not None else None,
            principal_user_id=owner_user.id if owner_user is not None else None,
            principal_is_admin=owner_user.is_admin if owner_user is not None else False,
        )
        self._latest_usage_totals: dict[str, int | None] = {}
        self._trace_step: BenchmarkTraceStep | None = None
        self._step_started_at = 0.0

    @property
    def latest_usage_totals(self) -> dict[str, int | None]:
        return dict(self._latest_usage_totals)

    @property
    def max_steps(self) -> int:
        return self._max_steps

    def build_initial_messages(self) -> list[dict[str, Any]]:
        return build_llm_messages(
            self._db,
            self._thread_id,
            current_user_message_id=self._user_message_id,
        )

    def initial_usage_totals(self) -> dict[str, int | None]:
        return {}

    def apply_usage_totals(self, usage_totals: dict[str, int | None]) -> None:
        self._latest_usage_totals = dict(usage_totals)
        self._run.input_tokens = usage_totals.get("input_tokens")
        self._run.output_tokens = usage_totals.get("output_tokens")
        self._run.cache_read_tokens = usage_totals.get("cache_read_tokens")
        self._run.cache_write_tokens = usage_totals.get("cache_write_tokens")
        self._db.add(self._run)

    def call_model_step(
        self,
        *,
        step_index: int,
        llm_messages: list[dict[str, Any]],
    ) -> ModelStepGenerator:
        self._step_started_at = time.monotonic()
        messages_snapshot = _redact_image_content(llm_messages)
        assistant_msg = call_model(llm_messages, self._db)
        step_usage = extract_usage_dict(assistant_msg, fields=USAGE_FIELDS)
        tool_calls = assistant_msg.get("tool_calls") or []
        assistant_content = assistant_msg.get("content") or ""
        self._trace_step = BenchmarkTraceStep(
            step=step_index,
            messages_sent=messages_snapshot,
            model_response={
                "content": assistant_content,
                "tool_calls": tool_calls,
                "usage": step_usage,
            },
        )
        if False:  # pragma: no cover - generator shape helper
            yield {}
        return assistant_msg

    def prepare_tool_calls(
        self,
        *,
        step: AssistantStepContext,
        llm_messages: list[dict[str, Any]],
    ) -> tuple[list[_PreparedToolCall], list[dict[str, Any]]]:
        sanitized_tool_calls = [canonicalize_tool_call(tool_call) for tool_call in step.tool_calls]
        llm_messages.append(
            {
                "role": "assistant",
                "content": step.assistant_content,
                "tool_calls": sanitized_tool_calls,
            }
        )
        prepared_calls: list[_PreparedToolCall] = []
        for tool_call in sanitized_tool_calls:
            decoded = decode_tool_call(tool_call)
            prepared_calls.append(
                _PreparedToolCall(
                    tool_call=tool_call,
                    tool_name=decoded.tool_name,
                    arguments=decoded.arguments,
                    raw_arguments=decoded.raw_arguments,
                    decode_error=decoded.decode_error,
                )
            )
        return prepared_calls, []

    def execute_prepared_tool_call(
        self,
        *,
        step: AssistantStepContext,
        prepared_tool_call: _PreparedToolCall,
        llm_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result = (
            tool_call_decode_error_result(
                tool_name=prepared_tool_call.tool_name,
                raw_arguments=prepared_tool_call.raw_arguments,
                decode_error=prepared_tool_call.decode_error,
            )
            if prepared_tool_call.decode_error is not None
            else execute_tool(
                prepared_tool_call.tool_name,
                prepared_tool_call.arguments,
                self._tool_context,
            )
        )
        llm_messages.append(
            {
                "role": "tool",
                "tool_call_id": prepared_tool_call.tool_call.get("id"),
                "name": prepared_tool_call.tool_name,
                "content": result.output_text,
            }
        )
        if (
            prepared_tool_call.decode_error is None
            and prepared_tool_call.tool_name in PROPOSAL_TOOL_NAMES
        ):
            self._state.proposal_inputs.append(
                {
                    "tool_name": prepared_tool_call.tool_name,
                    "arguments": dict(prepared_tool_call.arguments),
                }
            )

        if self._trace_step is not None:
            self._trace_step.tool_results.append(
                {
                    "tool_name": prepared_tool_call.tool_name,
                    "input": prepared_tool_call.arguments,
                    "output": result.output_json,
                    "status": result.status.value,
                }
            )
        return []

    def after_tool_turn(
        self,
        *,
        step: AssistantStepContext,
        llm_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self._db.commit()
        self._finalize_trace_step()
        return []

    def record_model_reasoning(self, *, step: AssistantStepContext) -> list[dict[str, Any]]:
        self._finalize_trace_step()
        return []

    def complete(self, *, step: AssistantStepContext) -> list[dict[str, Any]]:
        self._finalize_trace_step()
        self._state.final_assistant_content = step.assistant_content
        self._run.status = AgentRunStatus.COMPLETED
        self._db.add(self._run)
        self._db.commit()
        return []

    def fail_max_steps(self) -> list[dict[str, Any]]:
        self._finalize_trace_step()
        _mark_failed_run(
            self._db,
            self._run,
            self._state,
            error_text="maximum tool steps reached",
        )
        return []

    def fail_model_error(self, error: AgentModelError) -> list[dict[str, Any]]:
        self._finalize_trace_step()
        _mark_failed_run(self._db, self._run, self._state, error_text=str(error))
        return []

    def fail_unexpected_error(self, error: Exception) -> list[dict[str, Any]]:
        self._finalize_trace_step()
        _mark_failed_run(self._db, self._run, self._state, error_text=str(error))
        return []

    def _finalize_trace_step(self) -> None:
        if self._trace_step is None:
            return
        self._trace_step.wall_clock_ms = int(
            (time.monotonic() - self._step_started_at) * 1000
        )
        self._state.trace_steps.append(self._trace_step)
        self._trace_step = None


def run_benchmark_case(
    db: Session,
    *,
    text: str,
    attachments: list[BenchmarkAttachmentInput],
) -> BenchmarkCaseExecution:
    settings = resolve_runtime_settings(db)
    owner_user = (
        db.scalar(select(User).where(User.is_admin.is_(True)).order_by(User.created_at.asc()).limit(1))
        or db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    )
    if owner_user is None:
        raise ValueError("Benchmark execution requires at least one persisted user.")
    thread, user_message, run = _create_benchmark_run(
        db,
        text=text,
        attachments=attachments,
        model_name=settings.agent_model,
        owner_user=owner_user,
    )
    state = _BenchmarkRunState()
    overall_start = time.monotonic()

    adapter = _BenchmarkRunLoopAdapter(
        db=db,
        run=run,
        thread_id=thread.id,
        user_message_id=user_message.id,
        max_steps=max(settings.agent_max_steps, 1),
        state=state,
    )
    if _run_loop_outcome(adapter) == RunLoopOutcome.STOPPED:
        _mark_failed_run(
            db,
            run,
            state,
            error_text="benchmark run stopped unexpectedly",
        )

    total_wall_clock_ms = int((time.monotonic() - overall_start) * 1000)
    predictions = _predictions_from_proposals(state.proposal_inputs)
    db.refresh(run, attribute_names=["status", "error_text"])
    return BenchmarkCaseExecution(
        run_status=run.status.value,
        error=state.execution_error or run.error_text,
        predictions=predictions,
        trace_steps=state.trace_steps,
        total_usage=adapter.latest_usage_totals,
        total_wall_clock_ms=total_wall_clock_ms,
        final_assistant_content=state.final_assistant_content,
    )
