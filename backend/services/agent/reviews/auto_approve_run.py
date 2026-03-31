# CALLING SPEC:
# - Purpose: auto-approve pending `AgentChangeItem` rows for a completed run when policy is YOLO.
# - Inputs: SQLAlchemy session, run id, thread id, approval policy enum, and resolved actor name.
# - Outputs: none; persists review actions and applied rows via `approve_change_item`.
# - Side effects: database commits inside `approve_change_item`; structured logging on partial failure.
from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.enums_agent import AgentApprovalPolicy, AgentChangeStatus
from backend.models_agent import AgentChangeItem, AgentThread
from backend.models_finance import User
from backend.services.agent.reviews.workflow import approve_change_item
from backend.services.crud_policy import PolicyViolation

logger = logging.getLogger(__name__)

YOLO_APPROVE_NOTE = "yolo auto-approve"
_MAX_PASSES = 64


def maybe_auto_approve_after_completed_run(
    db: Session,
    *,
    run_id: str,
    thread_id: str,
    approval_policy: AgentApprovalPolicy,
) -> None:
    if approval_policy != AgentApprovalPolicy.YOLO:
        return
    thread = db.get(AgentThread, thread_id)
    if thread is None:
        logger.warning(
            "yolo auto-approve skipped scope=agent_yolo run_id=%s thread_id=%s reason=thread_missing",
            run_id,
            thread_id,
        )
        return
    owner = db.get(User, thread.owner_user_id)
    if owner is None:
        logger.warning(
            "yolo auto-approve skipped scope=agent_yolo run_id=%s thread_id=%s reason=owner_missing",
            run_id,
            thread_id,
        )
        return
    _auto_approve_pending_for_run(db, run_id=run_id, actor=owner.name)


def _auto_approve_pending_for_run(db: Session, *, run_id: str, actor: str) -> None:
    last_policy_detail: str | None = None
    for _ in range(_MAX_PASSES):
        pending = list(
            db.scalars(
                select(AgentChangeItem)
                .where(
                    AgentChangeItem.run_id == run_id,
                    AgentChangeItem.status == AgentChangeStatus.PENDING_REVIEW,
                )
                .order_by(AgentChangeItem.created_at.asc())
            )
        )
        if not pending:
            return
        progressed = False
        for item in pending:
            try:
                approve_change_item(
                    db,
                    item_id=item.id,
                    actor=actor,
                    note=YOLO_APPROVE_NOTE,
                )
                progressed = True
            except PolicyViolation as exc:
                last_policy_detail = exc.detail
                logger.info(
                    "yolo auto-approve deferred scope=agent_yolo run_id=%s item_id=%s detail=%s",
                    run_id,
                    item.id,
                    exc.detail,
                )
            except Exception as exc:
                logger.warning(
                    "yolo auto-approve item_error scope=agent_yolo run_id=%s item_id=%s",
                    run_id,
                    item.id,
                    exc_info=exc,
                )
        if not progressed:
            remaining = list(
                db.scalars(
                    select(AgentChangeItem.id).where(
                        AgentChangeItem.run_id == run_id,
                        AgentChangeItem.status == AgentChangeStatus.PENDING_REVIEW,
                    )
                )
            )
            logger.warning(
                "yolo auto-approve incomplete scope=agent_yolo run_id=%s remaining_pending=%s last_policy_detail=%s",
                run_id,
                remaining,
                last_policy_detail,
            )
            return
