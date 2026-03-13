# CALLING SPEC:
# - Purpose: implement focused service logic for `principals`.
# - Inputs: callers that import `backend/services/principals.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `principals`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
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
