# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for thread-scoped `agent proposals` routes.
# - Inputs: callers that import `backend/routers/agent_proposals.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for proposal list/get/create/update/delete.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.schemas_agent import (
    AgentProposalCreateRequest,
    AgentProposalDeleteRead,
    AgentProposalListQuery,
    AgentProposalListRead,
    AgentProposalRecordRead,
    AgentProposalUpdateRequest,
)
from backend.services.access_scope import load_agent_thread_for_principal
from backend.services.agent.proposal_http import (
    build_thread_tool_context,
    create_thread_proposal,
    get_thread_proposal,
    list_thread_proposals,
    remove_thread_proposal,
    update_thread_proposal,
)
from backend.services.agent.tool_args.read import ListProposalsArgs


router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)


def _require_agent_run_id(
    run_id: str | None = Header(default=None, alias="X-Bill-Helper-Agent-Run-Id"),
) -> str:
    normalized = (run_id or "").strip()
    if not normalized:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Bill-Helper-Agent-Run-Id header.",
        )
    return normalized


@router.get("/threads/{thread_id}/proposals", response_model=AgentProposalListRead)
def list_proposals_for_thread(
    thread_id: str,
    query: AgentProposalListQuery = Depends(),
    run_id: str = Depends(_require_agent_run_id),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentProposalListRead:
    load_agent_thread_for_principal(db, thread_id=thread_id, principal=principal)
    context = build_thread_tool_context(db, principal=principal, thread_id=thread_id, run_id=run_id)
    result = list_thread_proposals(
        context,
        query=ListProposalsArgs.model_validate(query.model_dump(exclude_none=True)),
    )
    return AgentProposalListRead.model_validate(result)


@router.get("/threads/{thread_id}/proposals/{proposal_id}", response_model=AgentProposalRecordRead)
def get_proposal_for_thread(
    thread_id: str,
    proposal_id: str,
    run_id: str = Depends(_require_agent_run_id),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentProposalRecordRead:
    load_agent_thread_for_principal(db, thread_id=thread_id, principal=principal)
    context = build_thread_tool_context(db, principal=principal, thread_id=thread_id, run_id=run_id)
    return AgentProposalRecordRead.model_validate(get_thread_proposal(context, proposal_id=proposal_id))


@router.post("/threads/{thread_id}/proposals", response_model=AgentProposalRecordRead, status_code=201)
def create_proposal_for_thread(
    thread_id: str,
    payload: AgentProposalCreateRequest,
    run_id: str = Depends(_require_agent_run_id),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentProposalRecordRead:
    load_agent_thread_for_principal(db, thread_id=thread_id, principal=principal)
    context = build_thread_tool_context(db, principal=principal, thread_id=thread_id, run_id=run_id)
    result = AgentProposalRecordRead.model_validate(
        create_thread_proposal(
            context,
            change_type=payload.change_type,
            payload_json=payload.payload_json,
        )
    )
    db.commit()
    return result


@router.patch("/threads/{thread_id}/proposals/{proposal_id}", response_model=AgentProposalRecordRead)
def update_proposal_for_thread(
    thread_id: str,
    proposal_id: str,
    payload: AgentProposalUpdateRequest,
    run_id: str = Depends(_require_agent_run_id),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentProposalRecordRead:
    load_agent_thread_for_principal(db, thread_id=thread_id, principal=principal)
    context = build_thread_tool_context(db, principal=principal, thread_id=thread_id, run_id=run_id)
    result = AgentProposalRecordRead.model_validate(
        update_thread_proposal(
            context,
            proposal_id=proposal_id,
            patch_map=payload.patch_map,
        )
    )
    db.commit()
    return result


@router.delete("/threads/{thread_id}/proposals/{proposal_id}", response_model=AgentProposalDeleteRead)
def delete_proposal_for_thread(
    thread_id: str,
    proposal_id: str,
    run_id: str = Depends(_require_agent_run_id),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentProposalDeleteRead:
    load_agent_thread_for_principal(db, thread_id=thread_id, principal=principal)
    context = build_thread_tool_context(db, principal=principal, thread_id=thread_id, run_id=run_id)
    result = AgentProposalDeleteRead.model_validate(remove_thread_proposal(context, proposal_id=proposal_id))
    db.commit()
    return result
