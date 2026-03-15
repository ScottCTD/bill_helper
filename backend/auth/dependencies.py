# CALLING SPEC:
# - Purpose: provide the `dependencies` module.
# - Inputs: callers that import `backend/auth/dependencies.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `dependencies`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.principals import build_request_principal
from backend.services.sessions import load_session_by_token

from .contracts import AUTHORIZATION_SCHEME, AuthenticatedSessionContext, RequestPrincipal


def _parse_bearer_token(authorization_header: str | None) -> str | None:
    if authorization_header is None:
        return None
    scheme, _, token = authorization_header.partition(" ")
    if scheme.strip().lower() != AUTHORIZATION_SCHEME.lower():
        return None
    normalized_token = token.strip()
    return normalized_token or None


def _build_authenticated_session_context(
    *,
    db: Session,
    token: str | None,
    missing_detail: str,
) -> AuthenticatedSessionContext:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=missing_detail,
        )
    session_row = load_session_by_token(db, token=token)
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )
    return AuthenticatedSessionContext(
        principal=build_request_principal(user=session_row.user, session=session_row),
        session_token=token,
    )


def get_current_auth_context(
    db: Session = Depends(get_db),
    authorization_header: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedSessionContext:
    token = _parse_bearer_token(authorization_header)
    return _build_authenticated_session_context(
        db=db,
        token=token,
        missing_detail="Missing or invalid Authorization header.",
    )


def get_current_principal(
    auth_context: AuthenticatedSessionContext = Depends(get_current_auth_context),
) -> RequestPrincipal:
    return auth_context.principal


def get_current_principal_from_cookie(
    cookie_name: str,
):
    def _dependency(
        db: Session = Depends(get_db),
        session_cookie: str | None = Cookie(default=None, alias=cookie_name),
    ) -> RequestPrincipal:
        return _build_authenticated_session_context(
            db=db,
            token=session_cookie,
            missing_detail="Missing workspace session cookie.",
        ).principal

    return _dependency


def require_admin_principal(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> RequestPrincipal:
    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin principal can access this resource.",
        )
    return principal
