from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.config import get_settings
from backend.database import SessionLocal, get_db
from backend.enums import AgentChangeStatus, AgentMessageRole, AgentRunStatus
from backend.models import (
    AgentChangeItem,
    AgentMessage,
    AgentMessageAttachment,
    AgentRun,
    AgentThread,
)
from backend.schemas import (
    AgentChangeItemApproveRequest,
    AgentChangeItemRead,
    AgentChangeItemRejectRequest,
    AgentRunRead,
    AgentThreadCreate,
    AgentThreadDetailRead,
    AgentThreadRead,
    AgentThreadSummaryRead,
)
from backend.services.agent import (
    AgentRuntimeUnavailable,
    approve_change_item,
    ensure_agent_available,
    interrupt_agent_run,
    reject_change_item,
    run_existing_agent_run,
    run_existing_agent_run_stream,
    start_agent_run,
)
from backend.services.agent.context_tokens import count_context_tokens
from backend.services.agent.message_history import build_llm_messages
from backend.services.agent.serializers import (
    change_item_to_schema,
    message_to_schema,
    run_to_schema,
    thread_summary_to_schema,
    thread_to_schema,
)
from backend.services.agent.tools import build_openai_tool_schemas
from backend.services.runtime_settings import resolve_runtime_settings

router = APIRouter(prefix="/agent", tags=["agent"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_thread_or_404(db: Session, thread_id: str) -> AgentThread:
    thread = db.get(AgentThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread


def _sanitize_title(content: str) -> str | None:
    normalized = " ".join(content.split()).strip()
    if not normalized:
        return None
    if len(normalized) <= 72:
        return normalized
    return f"{normalized[:69]}..."


def _normalize_optional_text(value: str | None) -> str:
    return (value or "").strip()


def _current_context_tokens_for_thread(
    db: Session,
    *,
    thread: AgentThread,
    model_name: str,
) -> int | None:
    runs_by_newest = sorted(thread.runs, key=lambda run: run.created_at, reverse=True)
    for run in runs_by_newest:
        if run.status == AgentRunStatus.RUNNING and run.context_tokens is not None:
            return run.context_tokens

    current_messages = build_llm_messages(db, thread.id, current_user_message_id=None)
    current_context_tokens = count_context_tokens(
        model_name=model_name,
        messages=current_messages,
        tools=build_openai_tool_schemas(),
    )
    if current_context_tokens is not None:
        return current_context_tokens

    for run in runs_by_newest:
        if run.context_tokens is not None:
            return run.context_tokens
    return None


def _thread_summary_rows(db: Session) -> list[AgentThreadSummaryRead]:
    threads = list(db.scalars(select(AgentThread).order_by(AgentThread.updated_at.desc())))
    running_thread_ids = set(
        db.scalars(
            select(AgentRun.thread_id)
            .where(AgentRun.status == AgentRunStatus.RUNNING)
            .distinct()
        )
    )
    summaries: list[AgentThreadSummaryRead] = []
    for thread in threads:
        last_message = db.scalar(
            select(AgentMessage.content_markdown)
            .where(AgentMessage.thread_id == thread.id)
            .order_by(AgentMessage.created_at.desc())
            .limit(1)
        )
        pending_change_count = int(
            db.scalar(
                select(func.count(AgentChangeItem.id))
                .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
                .where(
                    AgentRun.thread_id == thread.id,
                    AgentChangeItem.status == AgentChangeStatus.PENDING_REVIEW,
                )
            )
            or 0
        )
        summaries.append(
            thread_summary_to_schema(
                thread,
                last_message_preview=(last_message[:120] if last_message else None),
                pending_change_count=pending_change_count,
                has_running_run=thread.id in running_thread_ids,
            )
        )
    return summaries


def _thread_attachment_directories(thread: AgentThread) -> set[Path]:
    upload_root = (get_settings().data_dir / "agent_uploads").resolve()
    directories: set[Path] = set()
    for message in thread.messages:
        for attachment in message.attachments:
            directory = Path(attachment.file_path).parent
            resolved_directory = directory.resolve()
            if resolved_directory == upload_root:
                continue
            if upload_root in resolved_directory.parents:
                directories.add(resolved_directory)
    return directories


def _delete_attachment_directories(directories: set[Path]) -> None:
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        shutil.rmtree(directory, ignore_errors=True)


def _store_attachment_bytes(
    *,
    message_id: str,
    mime_type: str,
    original_filename: str | None,
    file_bytes: bytes,
) -> str:
    upload_root = get_settings().data_dir / "agent_uploads" / message_id
    upload_root.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_filename or "").suffix
    if not suffix:
        if mime_type == "image/png":
            suffix = ".png"
        elif mime_type == "image/jpeg":
            suffix = ".jpg"
        elif mime_type == "image/webp":
            suffix = ".webp"
        elif mime_type == "application/pdf":
            suffix = ".pdf"
        else:
            suffix = ".bin"
    file_path = upload_root / f"{uuid4()}{suffix}"
    file_path.write_bytes(file_bytes)
    return str(file_path)


def _run_agent_in_background(run_id: str) -> None:
    db = SessionLocal()
    try:
        run_existing_agent_run(db, run_id)
    finally:
        db.close()


def _sse_event(event_type: str, payload: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def _create_user_message_and_start_run(
    *,
    thread_id: str,
    content: str,
    files: list[UploadFile],
    db: Session,
) -> AgentRun:
    try:
        # Fail fast before persisting uploads/messages when no model credentials are configured.
        ensure_agent_available(db)
    except AgentRuntimeUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    settings = resolve_runtime_settings(db)
    thread = _get_thread_or_404(db, thread_id)
    clean_content = _normalize_optional_text(content)
    if not clean_content and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message must include text or at least one attachment.",
        )
    if len(files) > settings.agent_max_images_per_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many attachments. Max allowed is {settings.agent_max_images_per_message}.",
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image and PDF attachments are supported.",
            )
        file_bytes = await upload.read()
        if len(file_bytes) > settings.agent_max_image_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attachment too large. Max bytes allowed is {settings.agent_max_image_size_bytes}.",
            )
        path = _store_attachment_bytes(
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


@router.get("/threads", response_model=list[AgentThreadSummaryRead])
def list_threads(db: Session = Depends(get_db)) -> list[AgentThreadSummaryRead]:
    return _thread_summary_rows(db)


@router.post("/threads", response_model=AgentThreadRead, status_code=status.HTTP_201_CREATED)
def create_thread(payload: AgentThreadCreate | None = None, db: Session = Depends(get_db)) -> AgentThreadRead:
    thread = AgentThread(title=payload.title if payload else None)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread_to_schema(thread)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: str, db: Session = Depends(get_db)) -> None:
    thread = db.scalar(
        select(AgentThread)
        .where(AgentThread.id == thread_id)
        .options(
            selectinload(AgentThread.runs),
            selectinload(AgentThread.messages).selectinload(AgentMessage.attachments),
        )
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    if any(run.status == AgentRunStatus.RUNNING for run in thread.runs):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a thread while an agent run is still running.",
        )

    attachment_directories = _thread_attachment_directories(thread)
    db.delete(thread)
    db.commit()
    _delete_attachment_directories(attachment_directories)


@router.get("/threads/{thread_id}", response_model=AgentThreadDetailRead)
def get_thread_detail(thread_id: str, db: Session = Depends(get_db)) -> AgentThreadDetailRead:
    thread = db.scalar(
        select(AgentThread)
        .where(AgentThread.id == thread_id)
        .options(
            selectinload(AgentThread.messages).selectinload(AgentMessage.attachments),
            selectinload(AgentThread.runs).selectinload(AgentRun.events),
            selectinload(AgentThread.runs).selectinload(AgentRun.tool_calls),
            selectinload(AgentThread.runs)
            .selectinload(AgentRun.change_items)
            .selectinload(AgentChangeItem.review_actions),
        )
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    settings = resolve_runtime_settings(db)
    return AgentThreadDetailRead(
        thread=thread_to_schema(thread),
        messages=[message_to_schema(message, api_prefix=settings.api_prefix) for message in thread.messages],
        runs=[run_to_schema(run) for run in thread.runs],
        configured_model_name=settings.agent_model,
        current_context_tokens=_current_context_tokens_for_thread(
            db,
            thread=thread,
            model_name=settings.agent_model,
        ),
    )


@router.post("/threads/{thread_id}/messages", response_model=AgentRunRead)
async def send_thread_message(
    thread_id: str,
    content: str = Form(default=""),
    files: list[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_db),
) -> AgentRunRead:
    run = await _create_user_message_and_start_run(
        thread_id=thread_id,
        content=content,
        files=files,
        db=db,
    )
    Thread(target=_run_agent_in_background, args=(run.id,), daemon=True).start()
    return run_to_schema(run)


@router.post("/threads/{thread_id}/messages/stream")
async def send_thread_message_stream(
    thread_id: str,
    content: str = Form(default=""),
    files: list[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    run = await _create_user_message_and_start_run(
        thread_id=thread_id,
        content=content,
        files=files,
        db=db,
    )

    def stream_events():
        stream_finished = False
        try:
            for event in run_existing_agent_run_stream(db, run.id):
                event_type = str(event.get("type") or "event")
                payload = dict(event)
                yield _sse_event(event_type, payload)
            stream_finished = True
        finally:
            # If the client disconnects mid-stream, continue the run in background.
            if not stream_finished:
                Thread(target=_run_agent_in_background, args=(run.id,), daemon=True).start()

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_run(run_id: str, db: Session = Depends(get_db)) -> AgentRunRead:
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_calls),
            selectinload(AgentRun.change_items).selectinload(AgentChangeItem.review_actions),
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run_to_schema(run)


@router.post("/runs/{run_id}/interrupt", response_model=AgentRunRead)
def interrupt_run(run_id: str, db: Session = Depends(get_db)) -> AgentRunRead:
    run = interrupt_agent_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run_to_schema(run)


@router.post("/change-items/{item_id}/approve", response_model=AgentChangeItemRead)
def approve_item(
    item_id: str,
    payload: AgentChangeItemApproveRequest,
    db: Session = Depends(get_db),
) -> AgentChangeItemRead:
    settings = resolve_runtime_settings(db)
    try:
        item = approve_change_item(
            db,
            item_id=item_id,
            actor=settings.current_user_name,
            note=payload.note,
            payload_override=payload.payload_override,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("Only PENDING_REVIEW"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if "payload_override" in detail:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change item not found")
    return change_item_to_schema(item)


@router.post("/change-items/{item_id}/reject", response_model=AgentChangeItemRead)
def reject_item(
    item_id: str,
    payload: AgentChangeItemRejectRequest,
    db: Session = Depends(get_db),
) -> AgentChangeItemRead:
    settings = resolve_runtime_settings(db)
    try:
        item = reject_change_item(db, item_id=item_id, actor=settings.current_user_name, note=payload.note)
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("Only PENDING_REVIEW"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change item not found")
    return change_item_to_schema(item)


@router.get("/attachments/{attachment_id}")
def get_attachment(attachment_id: str, db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(AgentMessageAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    path = Path(attachment.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file is missing")
    return FileResponse(path, media_type=attachment.mime_type, filename=path.name)
