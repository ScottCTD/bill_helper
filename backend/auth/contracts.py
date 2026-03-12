from __future__ import annotations

from dataclasses import dataclass

AUTHORIZATION_SCHEME = "Bearer"


@dataclass(frozen=True, slots=True)
class RequestPrincipal:
    user_id: str
    user_name: str
    is_admin: bool = False
    session_id: str | None = None
    session_token_hash: str | None = None
    is_admin_impersonation: bool = False


def is_admin_principal(principal: RequestPrincipal) -> bool:
    return principal.is_admin
