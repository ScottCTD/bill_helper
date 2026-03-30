# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `agent_threads` routes.
# - Inputs: callers that import `backend/routers/agent_threads.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `agent_threads`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from collections.abc import Iterator
import json
from threading import Thread
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only, selectinload

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.database import get_session_maker
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
    AgentRunRead,
    AgentThreadCreate,
    AgentThreadDetailRead,
    AgentThreadRead,
    AgentThreadSummaryRead,
    AgentThreadUpdate,
)
from backend.services.access_scope import agent_thread_owner_filter, load_agent_thread_for_principal
from backend.services.agent.execution import (
    AgentExecutionPolicyError,
    create_user_message_and_start_run,
    current_context_tokens_for_thread,
    run_agent_in_background,
)
from backend.services.agent.runtime import AgentRuntimeUnavailable
from backend.services.agent.runtime import run_existing_agent_run_stream
from backend.services.agent.serializers import (
    message_to_schema,
    run_to_schema,
    thread_summary_to_schema,
    thread_to_schema,
)
from backend.services.agent.threads import AgentThreadNotFoundError, rename_thread_by_id
from backend.services.runtime_settings import resolve_runtime_settings

AgentSurface = Literal["app", "telegram"]

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)


def sse_event(event_type: str, payload: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def open_background_session() -> Session:
    return get_session_maker()()


async def create_user_message_run_or_503(
    *,
    thread_id: str,
    content: str,
    files: list[UploadFile],
    attachment_ids: list[str],
    surface: AgentSurface,
    db: Session,
    model_name: str | None,
) -> AgentRun:
    try:
        return await create_user_message_and_start_run(
            thread_id=thread_id,
            content=content,
            files=files,
            attachment_ids=attachment_ids,
            db=db,
            model_name=model_name,
            surface=surface,
        )
    except AgentRuntimeUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AgentExecutionPolicyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _thread_summary_rows(db: Session, *, principal: RequestPrincipal) -> list[AgentThreadSummaryRead]:
    threads = list(
        db.scalars(
            select(AgentThread)
            .where(agent_thread_owner_filter(principal))
            .order_by(AgentThread.updated_at.desc())
        )
    )
    running_thread_ids = set(
        db.scalars(
            select(AgentRun.thread_id)
            .join(AgentThread, AgentThread.id == AgentRun.thread_id)
            .where(AgentRun.status == AgentRunStatus.RUNNING)
            .where(agent_thread_owner_filter(principal))
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


@router.get("/threads", response_model=list[AgentThreadSummaryRead])
def list_threads(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[AgentThreadSummaryRead]:
    return _thread_summary_rows(db, principal=principal)


@router.post("/threads", response_model=AgentThreadRead, status_code=status.HTTP_201_CREATED)
def create_thread(
    payload: AgentThreadCreate | None = None,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentThreadRead:
    thread = AgentThread(owner_user_id=principal.user_id, title=payload.title if payload else None)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread_to_schema(thread)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    thread = load_agent_thread_for_principal(
        db,
        thread_id=thread_id,
        principal=principal,
        stmt=select(AgentThread).options(
            selectinload(AgentThread.runs),
            selectinload(AgentThread.messages).selectinload(AgentMessage.attachments),
        ),
    )

    if any(run.status == AgentRunStatus.RUNNING for run in thread.runs):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a thread while an agent run is still running.",
        )

    db.delete(thread)
    db.commit()


@router.patch("/threads/{thread_id}", response_model=AgentThreadRead)
def update_thread(
    thread_id: str,
    payload: AgentThreadUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentThreadRead:
    load_agent_thread_for_principal(db, thread_id=thread_id, principal=principal)
    try:
        result = rename_thread_by_id(db, thread_id=thread_id, title=payload.title)
    except AgentThreadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return thread_to_schema(result.thread)


@router.get("/threads/{thread_id}", response_model=AgentThreadDetailRead)
def get_thread_detail(
    thread_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentThreadDetailRead:
    thread = load_agent_thread_for_principal(
        db,
        thread_id=thread_id,
        principal=principal,
        stmt=select(AgentThread).options(
            selectinload(AgentThread.messages)
            .selectinload(AgentMessage.attachments)
            .selectinload(AgentMessageAttachment.user_file),
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
        ),
    )
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
    attachment_ids: list[str] = Form(default_factory=list),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentRunRead:
    load_agent_thread_for_principal(db, thread_id=thread_id, principal=principal)
    run = await create_user_message_run_or_503(
        thread_id=thread_id,
        content=content,
        files=files,
        attachment_ids=attachment_ids,
        surface=surface,
        db=db,
        model_name=model_name,
    )
    Thread(
        target=run_agent_in_background,
        kwargs={"run_id": run.id, "session_factory": open_background_session},
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
    attachment_ids: list[str] = Form(default_factory=list),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> StreamingResponse:
    load_agent_thread_for_principal(db, thread_id=thread_id, principal=principal)
    run = await create_user_message_run_or_503(
        thread_id=thread_id,
        content=content,
        files=files,
        attachment_ids=attachment_ids,
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
                yield sse_event(event_type, payload)
            stream_finished = True
        finally:
            if not stream_finished:
                Thread(
                    target=run_agent_in_background,
                    kwargs={"run_id": run.id, "session_factory": open_background_session},
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
