from __future__ import annotations

from dataclasses import dataclass

PRINCIPAL_HEADER_NAME = "X-Bill-Helper-Principal"


@dataclass(frozen=True, slots=True)
class RequestPrincipal:
    user_id: str
    user_name: str
    is_admin: bool = False


def normalize_principal_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def is_admin_principal(principal: RequestPrincipal) -> bool:
    return principal.is_admin
