# CALLING SPEC:
# - Purpose: implement focused service logic for `lifecycle`.
# - Inputs: callers that import `backend/services/agent/runtime_support/lifecycle.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `lifecycle`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from backend.enums_agent import AgentRunEventType, AgentRunStatus
from backend.models_agent import AgentMessage, AgentRun, AgentRunEvent, AgentThread
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.runtime_state import (
    cancel_incomplete_tool_calls as _cancel_incomplete_tool_calls,
    load_run_snapshot as _load_run_snapshot,
    persist_final_message as _persist_final_message,
    persist_run_event as _persist_run_event,
    run_has_terminal_event as _run_has_terminal_event,
    utc_now,
)
from backend.services.runtime_settings import resolve_runtime_settings
from backend.validation.runtime_settings import normalize_text_or_none


ContextTokenCalculator = Callable[..., int | None]


@dataclass(slots=True)
class ExistingRunResolution:
    state: str
    run: AgentRun | None = None
    thread: AgentThread | None = None
    terminal_event: AgentRunEvent | None = None


def create_run(
    db: Session,
    *,
    thread: AgentThread,
    user_message: AgentMessage,
    calculate_context_tokens: ContextTokenCalculator,
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


def run_is_stopped(db: Session, run: AgentRun) -> bool:
    db.refresh(run, attribute_names=["status"])
    return run.status != AgentRunStatus.RUNNING


def persist_terminal_run_state(
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


def resolve_existing_run(db: Session, run_id: str) -> ExistingRunResolution:
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

    terminal_event = persist_terminal_run_state(
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


def interrupt_run(
    db: Session,
    *,
    run_id: str,
    reason: str,
) -> AgentRun | None:
    run = db.get(AgentRun, run_id)
    if run is None:
        return None
    if run.status != AgentRunStatus.RUNNING:
        return _load_run_snapshot(db, run.id)

    thread = db.get(AgentThread, run.thread_id)
    _cancel_incomplete_tool_calls(db, run)
    persist_terminal_run_state(
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
