from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.schemas_agent import (
    AgentChangeItemApproveRequest,
    AgentChangeItemRead,
    AgentChangeItemRejectRequest,
    AgentChangeItemReopenRequest,
)
from backend.services.access_scope import load_change_item_for_principal
from backend.services.crud_policy import PolicyViolation
from backend.services.agent.reviews.workflow import (
    approve_change_item,
    reject_change_item,
    reopen_change_item,
)
from backend.services.agent.serializers import change_item_to_schema

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)


@router.post("/change-items/{item_id}/approve", response_model=AgentChangeItemRead)
def approve_item(
    item_id: str,
    payload: AgentChangeItemApproveRequest,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentChangeItemRead:
    load_change_item_for_principal(db, item_id=item_id, principal=principal)
    item = approve_change_item(
        db,
        item_id=item_id,
        actor=principal.user_name,
        note=payload.note,
        payload_override=payload.payload_override,
    )
    if item is None:
        raise PolicyViolation.not_found("Change item not found")
    return change_item_to_schema(item)


@router.post("/change-items/{item_id}/reject", response_model=AgentChangeItemRead)
def reject_item(
    item_id: str,
    payload: AgentChangeItemRejectRequest,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentChangeItemRead:
    load_change_item_for_principal(db, item_id=item_id, principal=principal)
    item = reject_change_item(
        db,
        item_id=item_id,
        actor=principal.user_name,
        note=payload.note,
        payload_override=payload.payload_override,
    )
    if item is None:
        raise PolicyViolation.not_found("Change item not found")
    return change_item_to_schema(item)


@router.post("/change-items/{item_id}/reopen", response_model=AgentChangeItemRead)
def reopen_item(
    item_id: str,
    payload: AgentChangeItemReopenRequest,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentChangeItemRead:
    load_change_item_for_principal(db, item_id=item_id, principal=principal)
    item = reopen_change_item(
        db,
        item_id=item_id,
        actor=principal.user_name,
        note=payload.note,
        payload_override=payload.payload_override,
    )
    if item is None:
        raise PolicyViolation.not_found("Change item not found")
    return change_item_to_schema(item)
