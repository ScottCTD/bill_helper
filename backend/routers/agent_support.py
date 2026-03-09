from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_admin_principal
from backend.config import get_settings
from backend.database import get_session_maker
from backend.models_agent import AgentRun
from backend.services.agent.execution import (
    AgentExecutionPolicyError,
    create_user_message_and_start_run,
)
from backend.services.agent.runtime import AgentRuntimeUnavailable

AgentSurface = Literal["app", "telegram"]

AGENT_ROUTER_KWARGS = {
    "prefix": "/agent",
    "tags": ["agent"],
    "dependencies": [Depends(require_admin_principal)],
}


def sse_event(event_type: str, payload: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def agent_upload_root() -> Path:
    return get_settings().data_dir / "agent_uploads"


def open_background_session() -> Session:
    return get_session_maker()()


async def create_user_message_run_or_503(
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
            upload_root=agent_upload_root(),
            db=db,
            model_name=model_name,
            surface=surface,
        )
    except AgentRuntimeUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AgentExecutionPolicyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
