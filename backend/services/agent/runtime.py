from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.enums import AgentMessageRole, AgentRunStatus, AgentToolCallStatus
from backend.models import AgentChangeItem, AgentMessage, AgentRun, AgentThread, AgentToolCall
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.model_client import AgentModelError, OpenRouterModelClient
from backend.services.agent.tools import ToolContext, build_openai_tool_schemas, execute_tool
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


def ensure_agent_available(db: Session) -> None:
    settings = resolve_runtime_settings(db)
    if not settings.openrouter_api_key:
        raise AgentRuntimeUnavailable(
            "Agent runtime is not configured: set OPENROUTER_API_KEY (or BILL_HELPER_OPENROUTER_API_KEY)."
        )


def _build_model_client(db: Session) -> OpenRouterModelClient:
    settings = resolve_runtime_settings(db)
    return OpenRouterModelClient(
        api_key=settings.openrouter_api_key or "",
        base_url=settings.openrouter_base_url,
        model_name=settings.agent_model,
        tools=build_openai_tool_schemas(),
        retry_max_attempts=settings.agent_retry_max_attempts,
        retry_initial_wait_seconds=settings.agent_retry_initial_wait_seconds,
        retry_max_wait_seconds=settings.agent_retry_max_wait_seconds,
        retry_backoff_multiplier=settings.agent_retry_backoff_multiplier,
    )


def _call_openrouter(messages: list[dict[str, Any]], db: Session) -> dict[str, Any]:
    # Kept as a stable seam so tests can monkeypatch model responses.
    return _build_model_client(db).complete(messages)


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
) -> dict[str, Any]:
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

    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id"),
        "name": name,
        "content": result.output_text,
    }


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
    usage_totals: dict[str, int | None] = {
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cache_read_tokens": run.cache_read_tokens,
        "cache_write_tokens": run.cache_write_tokens,
    }

    try:
        for _ in range(max_steps):
            assistant_message = _call_openrouter(llm_messages, db)
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
                    llm_messages.append(
                        _record_tool_call_and_result(
                            db,
                            run=run,
                            tool_call=tool_call,
                            tool_context=tool_context,
                        )
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


def run_agent_turn(db: Session, thread: AgentThread, user_message: AgentMessage) -> AgentRun:
    run = start_agent_run(db, thread, user_message)
    return _execute_agent_run(db, thread=thread, run=run)
