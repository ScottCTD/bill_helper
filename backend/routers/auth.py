from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.schemas_auth import AuthLoginRequest, AuthLoginResponse, AuthSessionRead, AuthUserRead
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
    return AuthLoginResponse(
        token=token,
        user=AuthUserRead.model_validate(user),
        session_id=session_row.id,
        is_admin_impersonation=session_row.is_admin_impersonation,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
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


@router.get("/me", response_model=AuthSessionRead)
def get_me(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AuthSessionRead:
    return _auth_session_payload(principal=principal)
