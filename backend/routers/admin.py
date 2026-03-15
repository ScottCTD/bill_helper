# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `admin` routes.
# - Inputs: callers that import `backend/routers/admin.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `admin`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import require_admin_principal
from backend.database import get_db
from backend.schemas_auth import (
    AdminSessionRead,
    AdminUserCreate,
    AdminUserPasswordReset,
    AdminUserUpdate,
    AuthLoginResponse,
    AuthUserRead,
)
from backend.schemas_finance import UserRead
from backend.services.agent_workspace import (
    queue_best_effort_user_workspace_start,
    queue_best_effort_user_workspace_stop,
)
from backend.services.sessions import (
    count_active_sessions_for_user,
    create_session,
    list_active_sessions,
    load_session_by_id,
    revoke_session_by_id,
)
from backend.services.users import (
    build_user_read,
    create_user_for_admin,
    delete_user_for_admin,
    reset_user_password_for_admin,
    update_user_for_admin,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.get("/users", response_model=list[UserRead])
def list_admin_users(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> list[UserRead]:
    from backend.services.users import list_user_reads

    return list_user_reads(db, principal=principal)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_admin_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> UserRead:
    user = create_user_for_admin(
        db,
        command=payload,
        principal=principal,
    )
    db.commit()
    db.refresh(user)
    return build_user_read(db, user=user, principal_user_id=principal.user_id)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_admin_user(
    user_id: str,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> UserRead:
    user = update_user_for_admin(
        db,
        user_id=user_id,
        patch=payload,
        principal=principal,
    )
    db.commit()
    db.refresh(user)
    return build_user_read(db, user=user, principal_user_id=principal.user_id)


@router.post("/users/{user_id}/reset-password", response_model=UserRead)
def reset_admin_user_password(
    user_id: str,
    payload: AdminUserPasswordReset,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> UserRead:
    user = reset_user_password_for_admin(
        db,
        user_id=user_id,
        command=payload,
        principal=principal,
    )
    db.commit()
    db.refresh(user)
    return build_user_read(db, user=user, principal_user_id=principal.user_id)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_user(
    user_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> None:
    delete_user_for_admin(db, user_id=user_id, principal=principal)
    db.commit()


@router.post("/users/{user_id}/login-as", response_model=AuthLoginResponse)
def login_as_user(
    user_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> AuthLoginResponse:
    from backend.services.access_scope import load_user_for_principal

    user = load_user_for_principal(db, user_id=user_id, principal=principal)
    token, session_row = create_session(
        db,
        user=user,
        is_admin_impersonation=True,
    )
    db.commit()
    queue_best_effort_user_workspace_start(user_id=user.id)
    return AuthLoginResponse(
        token=token,
        user=AuthUserRead.model_validate(user),
        session_id=session_row.id,
        is_admin_impersonation=True,
    )


@router.get("/sessions", response_model=list[AdminSessionRead])
def list_admin_sessions(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> list[AdminSessionRead]:
    return [
        AdminSessionRead(
            id=session_row.id,
            user_id=session_row.user_id,
            user_name=session_row.user.name,
            is_admin=session_row.user.is_admin,
            is_admin_impersonation=session_row.is_admin_impersonation,
            created_at=session_row.created_at,
            expires_at=session_row.expires_at,
            is_current=session_row.id == principal.session_id,
        )
        for session_row in list_active_sessions(db)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> None:
    session_row = load_session_by_id(db, session_id=session_id)
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    deleted = revoke_session_by_id(db, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if count_active_sessions_for_user(db, user_id=session_row.user_id) == 0:
        queue_best_effort_user_workspace_stop(user_id=session_row.user_id)
    db.commit()
