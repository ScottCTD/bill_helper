# CALLING SPEC:
# - Purpose: implement focused service logic for `threads`.
# - Inputs: callers that import `backend/services/agent/threads.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `threads`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models_agent import AgentRun, AgentThread
from backend.models_shared import utc_now
from backend.validation.agent_threads import validate_thread_title


class AgentThreadNotFoundError(LookupError):
    pass


@dataclass(slots=True)
class ThreadRenameResult:
    thread: AgentThread
    previous_title: str | None


def rename_thread_by_id(
    db: Session,
    *,
    thread_id: str,
    title: str,
) -> ThreadRenameResult:
    thread = db.get(AgentThread, thread_id)
    if thread is None:
        raise AgentThreadNotFoundError("Thread not found")
    return _persist_thread_title(db, thread=thread, title=title)


def rename_thread_for_run(
    db: Session,
    *,
    run_id: str,
    title: str,
) -> ThreadRenameResult:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise AgentThreadNotFoundError("Thread not found")
    thread = db.get(AgentThread, run.thread_id)
    if thread is None:
        raise AgentThreadNotFoundError("Thread not found")
    return _persist_thread_title(db, thread=thread, title=title)


def _persist_thread_title(
    db: Session,
    *,
    thread: AgentThread,
    title: str,
) -> ThreadRenameResult:
    normalized = validate_thread_title(title)
    previous_title = thread.title
    thread.title = normalized
    thread.updated_at = utc_now()
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return ThreadRenameResult(thread=thread, previous_title=previous_title)
