# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `auth` routes.
# - Inputs: callers that import `backend/routers/auth.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `auth`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.schemas_auth import AuthLoginRequest, AuthLoginResponse, AuthSessionRead, AuthUserRead
from backend.routers.workspace import clear_workspace_cookie_on_logout
from backend.services.agent_workspace import (
    queue_best_effort_user_workspace_start,
    stop_user_workspace_best_effort,
)
from backend.services.crud_policy import PolicyViolation
from backend.services.sessions import create_session, revoke_current_session
from backend.services.users import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])

def _auth_session_payload(
    *,
    principal: RequestPrincipal,
) -> AuthSessionRead:
    return AuthSessionRead(
        user=AuthUserRead(
            id=principal.user_id,
            name=principal.user_name,
            is_admin=principal.is_admin,
        ),
        session_id=principal.session_id,
        is_admin_impersonation=principal.is_admin_impersonation,
    )


@router.post("/login", response_model=AuthLoginResponse)
def login(
    payload: AuthLoginRequest,
    db: Session = Depends(get_db),
) -> AuthLoginResponse:
    try:
        user, _ = authenticate_user(
            db,
            username=payload.username,
            password=payload.password,
        )
    except PolicyViolation as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    token, session_row = create_session(db, user=user)
    db.commit()
    queue_best_effort_user_workspace_start(user_id=user.id)
    return AuthLoginResponse(
        token=token,
        user=AuthUserRead.model_validate(user),
        session_id=session_row.id,
        is_admin_impersonation=session_row.is_admin_impersonation,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    if principal.session_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current session is missing a session id.",
    )
    revoke_current_session(db, session_id=principal.session_id)
    db.commit()
    clear_workspace_cookie_on_logout(response)
    stop_user_workspace_best_effort(user_id=principal.user_id)


@router.get("/me", response_model=AuthSessionRead)
def get_me(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AuthSessionRead:
    return _auth_session_payload(principal=principal)
