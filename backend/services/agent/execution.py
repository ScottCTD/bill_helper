# CALLING SPEC:
# - Purpose: implement focused service logic for `execution`.
# - Inputs: callers that import `backend/services/agent/execution.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `execution`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import UploadFile
from sqlalchemy.orm import Session
from starlette import status

from backend.database import open_session
from backend.enums_agent import AgentMessageRole, AgentRunStatus
from backend.models_agent import AgentMessage, AgentMessageAttachment, AgentRun, AgentThread
from backend.services.agent.attachments import create_message_attachment
from backend.services.agent.context_tokens import count_context_tokens
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.runtime import (
    ensure_agent_available,
    run_existing_agent_run,
    start_agent_run,
)
from backend.services.agent.tool_runtime import build_openai_tool_schemas
from backend.services.user_files import SOURCE_TYPE_AGENT_ATTACHMENT, STORAGE_AREA_UPLOAD, store_user_file_bytes
from backend.services.runtime_settings import resolve_runtime_settings
from backend.validation.runtime_settings import normalize_text_or_none


@dataclass(slots=True)
class AgentExecutionPolicyError(Exception):
    detail: str
    status_code: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

    fallback_model_name = next(
        (run.model_name for run in runs_by_newest if run.model_name),
        model_name,
    )

    current_messages = build_llm_messages(
        db,
        thread.id,
        current_user_message_id=None,
        model_name=fallback_model_name,
    )
    current_context_tokens = count_context_tokens(
        model_name=fallback_model_name,
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
    db: Session,
    model_name: str | None = None,
    surface: str = "app",
) -> AgentRun:
    settings = resolve_runtime_settings(db)
    selected_model_name = normalize_text_or_none(model_name) or settings.agent_model
    if selected_model_name.casefold() not in {
        available_model.casefold() for available_model in settings.available_agent_models
    }:
        raise AgentExecutionPolicyError(
            detail="Selected model is not enabled in runtime settings.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    ensure_agent_available(db, model_name=selected_model_name)

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
        user_file = store_user_file_bytes(
            db,
            owner_user_id=thread.owner_user_id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            mime_type=mime_type,
            file_bytes=file_bytes,
            original_filename=upload.filename,
        )
        create_message_attachment(
            db,
            message_id=user_message.id,
            user_file=user_file,
        )

    thread.updated_at = utc_now()
    db.add(thread)
    db.commit()
    db.refresh(user_message)
    db.refresh(user_message, attribute_names=["attachments"])
    return start_agent_run(
        db,
        thread,
        user_message,
        model_name=selected_model_name,
        surface=surface,
    )


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
