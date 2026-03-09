from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.principals import ensure_request_principal

from .contracts import PRINCIPAL_HEADER_NAME, RequestPrincipal
from .dev_session import resolve_development_principal_identity


def get_or_create_current_principal(
    db: Session = Depends(get_db),
    principal_header: str | None = Header(default=None, alias=PRINCIPAL_HEADER_NAME),
) -> RequestPrincipal:
    identity = resolve_development_principal_identity(principal_header)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {PRINCIPAL_HEADER_NAME} header.",
        )
    return ensure_request_principal(db, principal_name=identity.user_name)


def require_admin_principal(
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> RequestPrincipal:
    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin principal can access this resource.",
        )
    return principal
