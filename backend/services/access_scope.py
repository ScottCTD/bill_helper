from __future__ import annotations

from sqlalchemy import Select, or_, select, true
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal, is_admin_principal
from backend.models_finance import Account, Entry, EntryGroup, User
from backend.services.crud_policy import PolicyViolation


def account_owner_filter(principal: RequestPrincipal):
    if is_admin_principal(principal):
        return true()
    return or_(Account.owner_user_id == principal.user_id, Account.owner_user_id.is_(None))


def entry_owner_filter(principal: RequestPrincipal):
    if is_admin_principal(principal):
        return true()
    return or_(Entry.owner_user_id == principal.user_id, Entry.owner_user_id.is_(None))


def group_owner_filter(principal: RequestPrincipal):
    if is_admin_principal(principal):
        return true()
    return or_(EntryGroup.owner_user_id == principal.user_id, EntryGroup.owner_user_id.is_(None))


def get_account_for_principal_or_404(
    db: Session,
    *,
    account_id: str,
    principal: RequestPrincipal,
) -> Account:
    return load_account_for_principal(db, account_id=account_id, principal=principal)


def load_account_for_principal(
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
        raise PolicyViolation.not_found("Account not found")
    return account


def get_entry_for_principal_or_404(
    db: Session,
    *,
    entry_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[Entry]] | None = None,
) -> Entry:
    return load_entry_for_principal(
        db,
        entry_id=entry_id,
        principal=principal,
        stmt=stmt,
    )


def load_entry_for_principal(
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
        raise PolicyViolation.not_found("Entry not found")
    return entry


def get_user_for_principal_or_404(
    db: Session,
    *,
    user_id: str,
    principal: RequestPrincipal,
) -> User:
    return load_user_for_principal(db, user_id=user_id, principal=principal)


def load_user_for_principal(
    db: Session,
    *,
    user_id: str,
    principal: RequestPrincipal,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise PolicyViolation.not_found("User not found")
    if not is_admin_principal(principal) and user.id != principal.user_id:
        raise PolicyViolation.not_found("User not found")
    return user


def get_group_for_principal_or_404(
    db: Session,
    *,
    group_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[EntryGroup]] | None = None,
) -> EntryGroup:
    return load_group_for_principal(
        db,
        group_id=group_id,
        principal=principal,
        stmt=stmt,
    )


def load_group_for_principal(
    db: Session,
    *,
    group_id: str,
    principal: RequestPrincipal,
    stmt: Select[tuple[EntryGroup]] | None = None,
) -> EntryGroup:
    query = stmt if stmt is not None else select(EntryGroup)
    group = db.scalar(
        query.where(
            EntryGroup.id == group_id,
            group_owner_filter(principal),
        )
    )
    if group is None:
        raise PolicyViolation.not_found("Group not found")
    return group


def ensure_principal_can_assign_user(
    principal: RequestPrincipal,
    *,
    user_id: str,
) -> None:
    if is_admin_principal(principal) or user_id == principal.user_id:
        return
    raise PolicyViolation.forbidden(
        "Cannot assign resources to a different user.",
    )
