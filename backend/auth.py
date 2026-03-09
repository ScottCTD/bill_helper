from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.services.users import ensure_current_user

ADMIN_PRINCIPAL_NAME = "admin"


@dataclass(frozen=True, slots=True)
class RequestPrincipal:
    user_id: str
    user_name: str


def _normalize_principal_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def is_admin_principal_name(value: str | None) -> bool:
    normalized = _normalize_principal_name(value)
    return normalized is not None and normalized.lower() == ADMIN_PRINCIPAL_NAME


def is_admin_principal(principal: RequestPrincipal) -> bool:
    return is_admin_principal_name(principal.user_name)


def get_current_principal(
    db: Session = Depends(get_db),
    principal_header: str | None = Header(default=None, alias="X-Bill-Helper-Principal"),
) -> RequestPrincipal:
    configured = _normalize_principal_name(get_settings().current_user_name) or ADMIN_PRINCIPAL_NAME
    principal_name = _normalize_principal_name(principal_header) or configured
    user = ensure_current_user(db, principal_name)
    return RequestPrincipal(user_id=user.id, user_name=user.name)


def require_admin_principal(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> RequestPrincipal:
    if not is_admin_principal(principal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin principal can access this resource.",
        )
    return principal
