from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.auth.dependencies import require_admin_principal
from backend.database import get_db
from backend.models_agent import AgentChangeItem, AgentRun, AgentToolCall
from backend.schemas_agent import AgentRunRead, AgentToolCallRead
from backend.services.agent.runtime import interrupt_agent_run
from backend.services.agent.serializers import run_to_schema, tool_call_to_schema

AgentSurface = Literal["app", "telegram"]

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(require_admin_principal)],
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
