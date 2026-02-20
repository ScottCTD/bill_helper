from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.enums import AgentMessageRole, AgentRunStatus, AgentToolCallStatus
from backend.models import AgentChangeItem, AgentMessage, AgentRun, AgentThread, AgentToolCall
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.model_client import AgentModelError, LiteLLMModelClient, validate_litellm_environment
from backend.services.agent.tools import (
    INTERMEDIATE_UPDATE_TOOL_NAME,
    ToolContext,
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
class RecordedToolCall:
    llm_message: dict[str, Any]
    persisted_row: AgentToolCall


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
    db.commit()


def _load_run_snapshot(db: Session, run_id: str) -> AgentRun:
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
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


def _record_tool_call_and_result(
    db: Session,
    *,
    run: AgentRun,
    tool_call: dict[str, Any],
    tool_context: ToolContext,
) -> RecordedToolCall:
    function = tool_call.get("function") or {}
    name = str(function.get("name") or "")
    arguments = _parse_tool_arguments(function.get("arguments") or "{}")

    result = execute_tool(name, arguments, tool_context)
    tool_row = AgentToolCall(
        run_id=run.id,
        tool_name=name or "(unknown)",
        input_json=arguments,
        output_json=result.output_json,
        status=AgentToolCallStatus.OK if result.status == "ok" else AgentToolCallStatus.ERROR,
    )
    db.add(tool_row)
    db.flush()

    return RecordedToolCall(
        llm_message={
            "role": "tool",
            "tool_call_id": tool_call.get("id"),
            "name": name,
            "content": result.output_text,
        },
        persisted_row=tool_row,
    )


def _extract_reasoning_update_message(tool_call: AgentToolCall) -> str | None:
    if tool_call.tool_name != INTERMEDIATE_UPDATE_TOOL_NAME:
        return None

    output_json = tool_call.output_json if isinstance(tool_call.output_json, dict) else {}
    output_message = output_json.get("message")
    if isinstance(output_message, str):
        normalized_output = output_message.strip()
        if normalized_output:
            return normalized_output

    input_json = tool_call.input_json if isinstance(tool_call.input_json, dict) else {}
    input_message = input_json.get("message")
    if isinstance(input_message, str):
        normalized_input = input_message.strip()
        if normalized_input:
            return normalized_input
    return None


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

    run = AgentRun(
        thread_id=thread.id,
        user_message_id=user_message.id,
        status=AgentRunStatus.RUNNING,
        model_name=settings.agent_model,
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


def _execute_agent_run(
    db: Session,
    *,
    thread: AgentThread,
    run: AgentRun,
) -> AgentRun:
    settings = resolve_runtime_settings(db)
    max_steps = max(settings.agent_max_steps, 1)

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

            if tool_calls:
                llm_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": tool_calls,
                    }
                )
                for tool_call in tool_calls:
                    if _run_is_stopped(db, run):
                        return _load_run_snapshot(db, run.id)
                    recorded_tool_call = _record_tool_call_and_result(
                        db,
                        run=run,
                        tool_call=tool_call,
                        tool_context=tool_context,
                    )
                    llm_messages.append(
                        recorded_tool_call.llm_message
                    )
                    db.commit()
                continue

            _persist_final_message(
                db,
                thread,
                run,
                _final_assistant_content(assistant_content),
                status=AgentRunStatus.COMPLETED,
            )
            return _load_run_snapshot(db, run.id)

        _persist_final_message(
            db,
            thread,
            run,
            (
                "I reached the configured max tool steps before finishing. "
                "Please review the existing tool outputs and pending review items."
            ),
            status=AgentRunStatus.FAILED,
            error_text="maximum tool steps reached",
        )
        return _load_run_snapshot(db, run.id)
    except AgentModelError as exc:
        _persist_final_message(
            db,
            thread,
            run,
            (
                "I could not complete this run because the language model request failed.\n"
                f"Error: {str(exc)}"
            ),
            status=AgentRunStatus.FAILED,
            error_text=str(exc),
        )
        return _load_run_snapshot(db, run.id)
    except Exception as exc:  # pragma: no cover - defensive guard
        _persist_final_message(
            db,
            thread,
            run,
            "I encountered an internal error while processing this request.",
            status=AgentRunStatus.FAILED,
            error_text=str(exc),
        )
        return _load_run_snapshot(db, run.id)


def _run_terminal_stream_event(run: AgentRun) -> dict[str, Any]:
    if run.status == AgentRunStatus.COMPLETED:
        return {
            "type": "run_completed",
            "run_id": run.id,
            "assistant_message_id": run.assistant_message_id,
            "status": run.status.value,
            "error_text": run.error_text,
        }
    return {
        "type": "run_failed",
        "run_id": run.id,
        "assistant_message_id": run.assistant_message_id,
        "status": run.status.value,
        "error_text": run.error_text,
    }


def _execute_agent_run_stream(
    db: Session,
    *,
    thread: AgentThread,
    run: AgentRun,
) -> Iterator[dict[str, Any]]:
    settings = resolve_runtime_settings(db)
    max_steps = max(settings.agent_max_steps, 1)

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
                yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
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
                yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
                return

            _accumulate_usage_totals(usage_totals, _extract_usage(assistant_message))
            _apply_usage_totals_to_run(run, usage_totals)
            db.add(run)

            tool_calls = assistant_message.get("tool_calls") or []
            assistant_content = assistant_message.get("content") or ""

            if tool_calls:
                llm_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": tool_calls,
                    }
                )
                for tool_call in tool_calls:
                    if _run_is_stopped(db, run):
                        yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
                        return
                    function = tool_call.get("function") or {}
                    tool_name = str(function.get("name") or "(unknown)")
                    recorded_tool_call = _record_tool_call_and_result(
                        db,
                        run=run,
                        tool_call=tool_call,
                        tool_context=tool_context,
                    )
                    llm_messages.append(recorded_tool_call.llm_message)
                    db.commit()
                    reasoning_update_message = _extract_reasoning_update_message(recorded_tool_call.persisted_row)
                    if reasoning_update_message is not None:
                        yield {
                            "type": "reasoning_update",
                            "run_id": run.id,
                            "message": reasoning_update_message,
                        }
                    else:
                        yield {
                            "type": "tool_call",
                            "run_id": run.id,
                            "tool_name": tool_name,
                        }
                continue

            _persist_final_message(
                db,
                thread,
                run,
                _final_assistant_content(assistant_content),
                status=AgentRunStatus.COMPLETED,
            )
            yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
            return

        _persist_final_message(
            db,
            thread,
            run,
            (
                "I reached the configured max tool steps before finishing. "
                "Please review the existing tool outputs and pending review items."
            ),
            status=AgentRunStatus.FAILED,
            error_text="maximum tool steps reached",
        )
        yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
        return
    except AgentModelError as exc:
        _persist_final_message(
            db,
            thread,
            run,
            (
                "I could not complete this run because the language model request failed.\n"
                f"Error: {str(exc)}"
            ),
            status=AgentRunStatus.FAILED,
            error_text=str(exc),
        )
        yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
        return
    except Exception as exc:  # pragma: no cover - defensive guard
        _persist_final_message(
            db,
            thread,
            run,
            "I encountered an internal error while processing this request.",
            status=AgentRunStatus.FAILED,
            error_text=str(exc),
        )
        yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
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
        run.status = AgentRunStatus.FAILED
        run.error_text = "thread not found"
        run.completed_at = utc_now()
        db.add(run)
        db.commit()
        return _load_run_snapshot(db, run.id)

    return _execute_agent_run(db, thread=thread, run=run)


def run_existing_agent_run_stream(db: Session, run_id: str) -> Iterator[dict[str, Any]]:
    run = db.get(AgentRun, run_id)
    if run is None:
        yield {
            "type": "run_failed",
            "run_id": run_id,
            "assistant_message_id": None,
            "status": AgentRunStatus.FAILED.value,
            "error_text": "run not found",
        }
        return
    if run.status != AgentRunStatus.RUNNING:
        yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
        return

    thread = db.get(AgentThread, run.thread_id)
    if thread is None:
        run.status = AgentRunStatus.FAILED
        run.error_text = "thread not found"
        run.completed_at = utc_now()
        db.add(run)
        db.commit()
        yield _run_terminal_stream_event(_load_run_snapshot(db, run.id))
        return

    yield {"type": "run_started", "run_id": run.id}
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

    run.status = AgentRunStatus.FAILED
    run.error_text = reason
    run.completed_at = utc_now()
    thread = db.get(AgentThread, run.thread_id)
    if thread is not None:
        thread.updated_at = utc_now()
        db.add(thread)
    db.add(run)
    db.commit()
    return _load_run_snapshot(db, run.id)
