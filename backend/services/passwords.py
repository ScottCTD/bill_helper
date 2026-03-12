from __future__ import annotations

from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError, VerificationError


_RESET_REQUIRED_PASSWORD = "__bill_helper_reset_required_do_not_use__"


@dataclass(frozen=True, slots=True)
class PasswordVerificationResult:
    is_valid: bool
    needs_rehash: bool = False
    requires_reset: bool = False


def _password_hasher() -> PasswordHasher:
    return PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher().hash(password)


def password_reset_required_hash() -> str:
    return hash_password(_RESET_REQUIRED_PASSWORD)


def is_password_reset_required_hash(password_hash: str) -> bool:
    try:
        return bool(_password_hasher().verify(password_hash, _RESET_REQUIRED_PASSWORD))
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def verify_password(password_hash: str, password: str) -> PasswordVerificationResult:
    if is_password_reset_required_hash(password_hash):
        return PasswordVerificationResult(is_valid=False, requires_reset=True)

    try:
        is_valid = bool(_password_hasher().verify(password_hash, password))
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return PasswordVerificationResult(is_valid=False)
    return PasswordVerificationResult(
        is_valid=is_valid,
        needs_rehash=_password_hasher().check_needs_rehash(password_hash),
    )
