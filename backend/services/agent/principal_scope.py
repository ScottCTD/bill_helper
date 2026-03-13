# CALLING SPEC:
# - Purpose: implement focused service logic for `principal_scope`.
# - Inputs: callers that import `backend/services/agent/principal_scope.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `principal_scope`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.models_agent import AgentChangeItem, AgentRun, AgentThread
from backend.models_finance import User
from backend.services.principals import build_request_principal


def _principal_for_user(user: User | None) -> RequestPrincipal | None:
    if user is None:
        return None
    return build_request_principal(user=user)


def load_thread_owner_user(
    db: Session,
    *,
    thread_id: str,
) -> User | None:
    return db.scalar(
        select(User)
        .join(AgentThread, AgentThread.owner_user_id == User.id)
        .where(AgentThread.id == thread_id)
        .limit(1)
    )


def load_thread_principal(
    db: Session,
    *,
    thread_id: str,
) -> RequestPrincipal | None:
    return _principal_for_user(load_thread_owner_user(db, thread_id=thread_id))


def load_run_owner_user(
    db: Session,
    *,
    run_id: str,
) -> User | None:
    return db.scalar(
        select(User)
        .join(AgentThread, AgentThread.owner_user_id == User.id)
        .join(AgentRun, AgentRun.thread_id == AgentThread.id)
        .where(AgentRun.id == run_id)
        .limit(1)
    )


def load_run_principal(
    db: Session,
    *,
    run_id: str,
) -> RequestPrincipal | None:
    return _principal_for_user(load_run_owner_user(db, run_id=run_id))


def load_change_item_owner_user(
    db: Session,
    *,
    item_id: str,
) -> User | None:
    return db.scalar(
        select(User)
        .join(AgentThread, AgentThread.owner_user_id == User.id)
        .join(AgentRun, AgentRun.thread_id == AgentThread.id)
        .join(AgentChangeItem, AgentChangeItem.run_id == AgentRun.id)
        .where(AgentChangeItem.id == item_id)
        .limit(1)
    )


def load_change_item_principal(
    db: Session,
    *,
    item_id: str,
) -> RequestPrincipal | None:
    return _principal_for_user(load_change_item_owner_user(db, item_id=item_id))
