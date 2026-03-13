# CALLING SPEC:
# - Purpose: provide the `dependencies` module.
# - Inputs: callers that import `backend/auth/dependencies.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `dependencies`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.principals import build_request_principal
from backend.services.sessions import load_session_by_token

from .contracts import AUTHORIZATION_SCHEME, RequestPrincipal


def _parse_bearer_token(authorization_header: str | None) -> str | None:
    if authorization_header is None:
        return None
    scheme, _, token = authorization_header.partition(" ")
    if scheme.strip().lower() != AUTHORIZATION_SCHEME.lower():
        return None
    normalized_token = token.strip()
    return normalized_token or None


def get_current_principal(
    db: Session = Depends(get_db),
    authorization_header: str | None = Header(default=None, alias="Authorization"),
) -> RequestPrincipal:
    token = _parse_bearer_token(authorization_header)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
        )
    session_row = load_session_by_token(db, token=token)
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )
    return build_request_principal(user=session_row.user, session=session_row)


def require_admin_principal(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> RequestPrincipal:
    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin principal can access this resource.",
        )
    return principal
