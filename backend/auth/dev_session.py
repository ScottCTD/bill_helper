from __future__ import annotations

from dataclasses import dataclass

from backend.config import get_settings

from .contracts import normalize_principal_name


@dataclass(frozen=True, slots=True)
class DevelopmentPrincipalIdentity:
    user_name: str


def _admin_name_keys() -> set[str]:
    return {name.casefold() for name in get_settings().development_admin_principal_names}


def is_admin_principal_name(value: str | None) -> bool:
    normalized = normalize_principal_name(value)
    return normalized is not None and normalized.casefold() in _admin_name_keys()


def resolve_development_principal_identity(
    principal_header: str | None,
) -> DevelopmentPrincipalIdentity | None:
    normalized_name = normalize_principal_name(principal_header)
    if normalized_name is None:
        return None
    return DevelopmentPrincipalIdentity(user_name=normalized_name)
