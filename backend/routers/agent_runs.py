from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.models_agent import AgentChangeItem, AgentRun, AgentToolCall
from backend.schemas_agent import AgentRunRead, AgentToolCallRead
from backend.services.access_scope import load_agent_run_for_principal, load_tool_call_for_principal
from backend.services.agent.runtime import interrupt_agent_run
from backend.services.agent.serializers import run_to_schema, tool_call_to_schema

AgentSurface = Literal["app", "telegram"]

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def get_run(
    run_id: str,
    surface: AgentSurface | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentRunRead:
    run = load_agent_run_for_principal(
        db,
        run_id=run_id,
        principal=principal,
        stmt=select(AgentRun).options(
            selectinload(AgentRun.assistant_message),
            selectinload(AgentRun.events),
            selectinload(AgentRun.tool_calls),
            selectinload(AgentRun.change_items).selectinload(AgentChangeItem.review_actions),
        ),
    )
    return run_to_schema(run, surface=surface)


@router.get("/tool-calls/{tool_call_id}", response_model=AgentToolCallRead)
def get_tool_call(
    tool_call_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentToolCallRead:
    tool_call = load_tool_call_for_principal(db, tool_call_id=tool_call_id, principal=principal)
    return tool_call_to_schema(tool_call, include_payload=True)


@router.post("/runs/{run_id}/interrupt", response_model=AgentRunRead)
def interrupt_run(
    run_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentRunRead:
    load_agent_run_for_principal(db, run_id=run_id, principal=principal)
    run = interrupt_agent_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run_to_schema(run)
