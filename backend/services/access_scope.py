from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import Select, or_, select, true
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal
from backend.models_finance import Account, Entry, User


def is_admin_principal(principal: RequestPrincipal) -> bool:
    return principal.user_name.lower() == "admin"


def account_owner_filter(principal: RequestPrincipal):
    if is_admin_principal(principal):
        return true()
    return or_(Account.owner_user_id == principal.user_id, Account.owner_user_id.is_(None))


def entry_owner_filter(principal: RequestPrincipal):
    if is_admin_principal(principal):
        return true()
    return or_(Entry.owner_user_id == principal.user_id, Entry.owner_user_id.is_(None))


def get_account_for_principal_or_404(
    db: Session,
    *,
    account_id: str,
    principal: RequestPrincipal,
) -> Account:
    account = db.scalar(
        select(Account).where(
            Account.id == account_id,
            account_owner_filter(principal),
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def get_entry_for_principal_or_404(
    db: Session,
    *,
    entry_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[Entry]] | None = None,
) -> Entry:
    query = stmt if stmt is not None else select(Entry)
    entry = db.scalar(
        query.where(
            Entry.id == entry_id,
            Entry.is_deleted.is_(False),
            entry_owner_filter(principal),
        )
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


def get_user_for_principal_or_404(
    db: Session,
    *,
    user_id: str,
    principal: RequestPrincipal,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not is_admin_principal(principal) and user.id != principal.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def ensure_principal_can_assign_user(
    principal: RequestPrincipal,
    *,
    user_id: str,
) -> None:
    if is_admin_principal(principal) or user_id == principal.user_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot assign resources to a different user.",
    )
