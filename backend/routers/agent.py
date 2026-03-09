from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from threading import Thread
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, selectinload

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal, require_admin_principal
from backend.config import get_settings
from backend.database import get_db, get_session_maker
from backend.enums_agent import AgentChangeStatus, AgentRunStatus, SUPPORTED_AGENT_CHANGE_TYPES
from backend.models_agent import (
    AgentChangeItem,
    AgentMessage,
    AgentMessageAttachment,
    AgentRun,
    AgentThread,
    AgentToolCall,
)
from backend.schemas_agent import (
    AgentChangeItemApproveRequest,
    AgentChangeItemReopenRequest,
    AgentChangeItemRead,
    AgentChangeItemRejectRequest,
    AgentRunRead,
    AgentToolCallRead,
    AgentThreadCreate,
    AgentThreadDetailRead,
    AgentThreadRead,
    AgentThreadSummaryRead,
    AgentThreadUpdate,
)
from backend.services.agent.attachments import (
    delete_attachment_directories,
    thread_attachment_directories,
)
from backend.services.agent.execution import (
    AgentExecutionPolicyError,
    create_user_message_and_start_run,
    current_context_tokens_for_thread,
    run_agent_in_background,
)
from backend.services.agent.threads import AgentThreadNotFoundError, rename_thread_by_id
from backend.services.agent.reviews.workflow import approve_change_item, reject_change_item, reopen_change_item
from backend.services.agent.runtime import (
    AgentRuntimeUnavailable,
    interrupt_agent_run,
    run_existing_agent_run_stream,
)
from backend.services.agent.serializers import (
    change_item_to_schema,
    message_to_schema,
    run_to_schema,
    tool_call_to_schema,
    thread_summary_to_schema,
    thread_to_schema,
)
from backend.services.runtime_settings import resolve_runtime_settings

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(require_admin_principal)],
)

AgentSurface = Literal["app", "telegram"]


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
                    AgentChangeItem.change_type.in_(SUPPORTED_AGENT_CHANGE_TYPES),
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


def _sse_event(event_type: str, payload: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _agent_upload_root() -> Path:
    return get_settings().data_dir / "agent_uploads"


def _open_background_session() -> Session:
    return get_session_maker()()


async def _create_user_message_run_or_503(
    *,
    thread_id: str,
    content: str,
    files: list[UploadFile],
    surface: AgentSurface,
    db: Session,
    model_name: str | None,
) -> AgentRun:
    try:
        return await create_user_message_and_start_run(
            thread_id=thread_id,
            content=content,
            files=files,
            upload_root=_agent_upload_root(),
            db=db,
            model_name=model_name,
            surface=surface,
        )
    except AgentRuntimeUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AgentExecutionPolicyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


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

    attachment_directories = thread_attachment_directories(thread, upload_root=_agent_upload_root())
    db.delete(thread)
    db.commit()
    delete_attachment_directories(attachment_directories)


@router.patch("/threads/{thread_id}", response_model=AgentThreadRead)
def update_thread(
    thread_id: str,
    payload: AgentThreadUpdate,
    db: Session = Depends(get_db),
) -> AgentThreadRead:
    try:
        result = rename_thread_by_id(db, thread_id=thread_id, title=payload.title)
    except AgentThreadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return thread_to_schema(result.thread)


@router.get("/threads/{thread_id}", response_model=AgentThreadDetailRead)
def get_thread_detail(thread_id: str, db: Session = Depends(get_db)) -> AgentThreadDetailRead:
    thread = db.scalar(
        select(AgentThread)
        .where(AgentThread.id == thread_id)
        .options(
            selectinload(AgentThread.messages).selectinload(AgentMessage.attachments),
            selectinload(AgentThread.runs).selectinload(AgentRun.events),
            selectinload(AgentThread.runs).selectinload(AgentRun.assistant_message),
            selectinload(AgentThread.runs)
            .selectinload(AgentRun.tool_calls)
            .options(
                load_only(
                    AgentToolCall.id,
                    AgentToolCall.run_id,
                    AgentToolCall.llm_tool_call_id,
                    AgentToolCall.tool_name,
                    AgentToolCall.status,
                    AgentToolCall.created_at,
                    AgentToolCall.started_at,
                    AgentToolCall.completed_at,
                )
            ),
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
        runs=[run_to_schema(run, include_tool_payload=False) for run in thread.runs],
        configured_model_name=settings.agent_model,
        current_context_tokens=current_context_tokens_for_thread(
            db,
            thread=thread,
            model_name=settings.agent_model,
        ),
    )


@router.post("/threads/{thread_id}/messages", response_model=AgentRunRead)
async def send_thread_message(
    thread_id: str,
    content: str = Form(default=""),
    model_name: str | None = Form(default=None),
    surface: AgentSurface = Form(default="app"),
    files: list[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_db),
) -> AgentRunRead:
    run = await _create_user_message_run_or_503(
        thread_id=thread_id,
        content=content,
        files=files,
        surface=surface,
        db=db,
        model_name=model_name,
    )
    Thread(
        target=run_agent_in_background,
        kwargs={"run_id": run.id, "session_factory": _open_background_session},
        daemon=True,
    ).start()
    return run_to_schema(run)


@router.post("/threads/{thread_id}/messages/stream")
async def send_thread_message_stream(
    thread_id: str,
    content: str = Form(default=""),
    model_name: str | None = Form(default=None),
    surface: AgentSurface = Form(default="app"),
    files: list[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    run = await _create_user_message_run_or_503(
        thread_id=thread_id,
        content=content,
        files=files,
        surface=surface,
        db=db,
        model_name=model_name,
    )

    def stream_events() -> Iterator[str]:
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
                Thread(
                    target=run_agent_in_background,
                    kwargs={"run_id": run.id, "session_factory": _open_background_session},
                    daemon=True,
                ).start()

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
def get_run(
    run_id: str,
    surface: AgentSurface | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AgentRunRead:
    run = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
            selectinload(AgentRun.assistant_message),
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_calls),
            selectinload(AgentRun.change_items).selectinload(AgentChangeItem.review_actions),
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run_to_schema(run, surface=surface)


@router.get("/tool-calls/{tool_call_id}", response_model=AgentToolCallRead)
def get_tool_call(tool_call_id: str, db: Session = Depends(get_db)) -> AgentToolCallRead:
    tool_call = db.get(AgentToolCall, tool_call_id)
    if tool_call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool call not found")
    return tool_call_to_schema(tool_call, include_payload=True)


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
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> AgentChangeItemRead:
    try:
        item = approve_change_item(
            db,
            item_id=item_id,
            actor=principal.user_name,
            note=payload.note,
            payload_override=payload.payload_override,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail.endswith("cannot be approved again"):
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
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> AgentChangeItemRead:
    try:
        item = reject_change_item(
            db,
            item_id=item_id,
            actor=principal.user_name,
            note=payload.note,
            payload_override=payload.payload_override,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail.endswith("cannot be changed back to rejected"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if "payload_override" in detail:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change item not found")
    return change_item_to_schema(item)


@router.post("/change-items/{item_id}/reopen", response_model=AgentChangeItemRead)
def reopen_item(
    item_id: str,
    payload: AgentChangeItemReopenRequest,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> AgentChangeItemRead:
    try:
        item = reopen_change_item(
            db,
            item_id=item_id,
            actor=principal.user_name,
            note=payload.note,
            payload_override=payload.payload_override,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail.endswith("cannot be reopened"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if "payload_override" in detail:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
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
