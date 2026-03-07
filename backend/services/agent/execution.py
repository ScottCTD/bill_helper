from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import UploadFile
from sqlalchemy.orm import Session
from starlette import status

from backend.database import open_session
from backend.enums_agent import AgentMessageRole, AgentRunStatus
from backend.models_agent import AgentMessage, AgentMessageAttachment, AgentRun, AgentThread
from backend.services.agent.attachments import store_attachment_bytes
from backend.services.agent.context_tokens import count_context_tokens
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.runtime import (
    call_model,
    call_model_stream,
    ensure_agent_available,
    run_existing_agent_run,
    start_agent_run,
)
from backend.services.agent.tools import (
    ToolContext,
    ToolExecutionResult,
    build_openai_tool_schemas,
    execute_tool,
)
from backend.services.runtime_settings import ResolvedRuntimeSettings, resolve_runtime_settings


@dataclass(slots=True)
class AgentExecutionPolicyError(Exception):
    detail: str
    status_code: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_title(content: str) -> str | None:
    normalized = " ".join(content.split()).strip()
    if not normalized:
        return None
    if len(normalized) <= 72:
        return normalized
    return f"{normalized[:69]}..."


def _normalize_optional_text(value: str | None) -> str:
    return (value or "").strip()


def current_context_tokens_for_thread(
    db: Session,
    *,
    thread: AgentThread,
    model_name: str,
) -> int | None:
    runs_by_newest = sorted(thread.runs, key=lambda run: run.created_at, reverse=True)
    for run in runs_by_newest:
        if run.status == AgentRunStatus.RUNNING and run.context_tokens is not None:
            return run.context_tokens

    for run in runs_by_newest:
        if run.context_tokens is not None:
            return run.context_tokens

    current_messages = build_llm_messages(db, thread.id, current_user_message_id=None)
    current_context_tokens = count_context_tokens(
        model_name=model_name,
        messages=current_messages,
        tools=build_openai_tool_schemas(),
    )
    if current_context_tokens is not None:
        return current_context_tokens
    return None


async def create_user_message_and_start_run(
    *,
    thread_id: str,
    content: str,
    files: list[UploadFile],
    upload_root: Path,
    db: Session,
) -> AgentRun:
    ensure_agent_available(db)

    settings = resolve_runtime_settings(db)
    thread = db.get(AgentThread, thread_id)
    if thread is None:
        raise AgentExecutionPolicyError(
            detail="Thread not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    clean_content = _normalize_optional_text(content)
    if not clean_content and not files:
        raise AgentExecutionPolicyError(
            detail="Message must include text or at least one attachment.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if len(files) > settings.agent_max_images_per_message:
        raise AgentExecutionPolicyError(
            detail=f"Too many attachments. Max allowed is {settings.agent_max_images_per_message}.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user_message = AgentMessage(
        thread_id=thread.id,
        role=AgentMessageRole.USER,
        content_markdown=clean_content,
    )
    db.add(user_message)
    db.flush()

    for upload in files:
        mime_type = (upload.content_type or "").lower()
        if not (mime_type.startswith("image/") or mime_type == "application/pdf"):
            raise AgentExecutionPolicyError(
                detail="Only image and PDF attachments are supported.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        file_bytes = await upload.read()
        if len(file_bytes) > settings.agent_max_image_size_bytes:
            raise AgentExecutionPolicyError(
                detail=f"Attachment too large. Max bytes allowed is {settings.agent_max_image_size_bytes}.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        path = store_attachment_bytes(
            upload_root=upload_root,
            message_id=user_message.id,
            mime_type=mime_type,
            original_filename=upload.filename,
            file_bytes=file_bytes,
        )
        db.add(
            AgentMessageAttachment(
                message_id=user_message.id,
                mime_type=mime_type,
                original_filename=upload.filename,
                file_path=path,
            )
        )

    if thread.title is None:
        thread.title = _sanitize_title(clean_content) or f"Thread {thread.created_at.date().isoformat()}"
    thread.updated_at = utc_now()
    db.add(thread)
    db.commit()
    db.refresh(user_message)
    db.refresh(user_message, attribute_names=["attachments"])
    return start_agent_run(db, thread, user_message)


def run_agent_in_background(
    run_id: str,
    *,
    session_factory: Callable[[], Session] = open_session,
) -> None:
    db = session_factory()
    try:
        run_existing_agent_run(db, run_id)
    finally:
        db.close()


def build_messages_for_thread(
    db: Session,
    *,
    thread_id: str,
    current_user_message_id: str | None,
) -> list[dict[str, Any]]:
    """Stable entrypoint for benchmark/test harness message assembly."""
    return build_llm_messages(db, thread_id, current_user_message_id=current_user_message_id)


def complete_model_once(
    db: Session,
    *,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Stable entrypoint for one non-stream model completion."""
    return call_model(messages, db)


def complete_model_stream(
    db: Session,
    *,
    messages: list[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Stable entrypoint for streaming model completion."""
    return call_model_stream(messages, db)


def build_tool_context(db: Session, *, run_id: str) -> ToolContext:
    """Stable helper for constructing tool execution context."""
    return ToolContext(db=db, run_id=run_id)


def execute_tool_call(name: str, arguments: dict[str, Any], context: ToolContext) -> ToolExecutionResult:
    """Stable entrypoint for invoking one tool call."""
    return execute_tool(name, arguments, context)


def resolve_execution_settings(db: Session) -> ResolvedRuntimeSettings:
    """Stable settings accessor for execution consumers."""
    return resolve_runtime_settings(db)
