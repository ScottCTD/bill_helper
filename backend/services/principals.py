from __future__ import annotations

from backend.models_finance import User, UserSession
from backend.auth.contracts import RequestPrincipal


def build_request_principal(
    *,
    user: User,
    session: UserSession | None = None,
) -> RequestPrincipal:
    return RequestPrincipal(
        user_id=user.id,
        user_name=user.name,
        is_admin=user.is_admin,
        session_id=session.id if session is not None else None,
        session_token_hash=session.token_hash if session is not None else None,
        is_admin_impersonation=session.is_admin_impersonation if session is not None else False,
    )
