from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models_agent import AgentRun, AgentThread
from backend.models_shared import utc_now

THREAD_TITLE_MAX_LENGTH = 80
THREAD_TITLE_MAX_WORDS = 5


class AgentThreadNotFoundError(LookupError):
    pass


class AgentThreadTitleError(ValueError):
    pass


@dataclass(slots=True)
class ThreadRenameResult:
    thread: AgentThread
    previous_title: str | None


def normalize_thread_title(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def validate_thread_title(value: str) -> str:
    normalized = normalize_thread_title(value)
    if normalized is None:
        raise AgentThreadTitleError("thread title cannot be empty")
    if len(normalized) > THREAD_TITLE_MAX_LENGTH:
        raise AgentThreadTitleError(
            f"thread title must be {THREAD_TITLE_MAX_LENGTH} characters or fewer"
        )
    if len(normalized.split()) > THREAD_TITLE_MAX_WORDS:
        raise AgentThreadTitleError(
            f"thread title must be {THREAD_TITLE_MAX_WORDS} words or fewer"
        )
    return normalized


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