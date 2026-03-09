from __future__ import annotations

from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dev_session import is_admin_principal_name
from backend.models_finance import User
from backend.services.users import ensure_current_user


def build_request_principal(*, user: User) -> RequestPrincipal:
    return RequestPrincipal(
        user_id=user.id,
        user_name=user.name,
        is_admin=user.is_admin,
    )


def ensure_request_principal(
    db: Session,
    *,
    principal_name: str,
) -> RequestPrincipal:
    user = ensure_current_user(
        db,
        principal_name,
        is_admin=is_admin_principal_name(principal_name),
    )
    return build_request_principal(user=user)
