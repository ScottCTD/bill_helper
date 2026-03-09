from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal
from backend.database import get_db
from backend.routers.agent_support import AGENT_ROUTER_KWARGS
from backend.schemas_agent import (
    AgentChangeItemApproveRequest,
    AgentChangeItemRead,
    AgentChangeItemRejectRequest,
    AgentChangeItemReopenRequest,
)
from backend.services.agent.reviews.workflow import (
    approve_change_item,
    reject_change_item,
    reopen_change_item,
)
from backend.services.agent.serializers import change_item_to_schema

router = APIRouter(**AGENT_ROUTER_KWARGS)


def _raise_review_http_error(exc: ValueError, *, conflict_suffix: str) -> None:
    detail = str(exc)
    if detail.endswith(conflict_suffix):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
    if "payload_override" in detail:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc


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
        _raise_review_http_error(exc, conflict_suffix="cannot be approved again")
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
        _raise_review_http_error(exc, conflict_suffix="cannot be changed back to rejected")
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
        _raise_review_http_error(exc, conflict_suffix="cannot be reopened")
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change item not found")
    return change_item_to_schema(item)
