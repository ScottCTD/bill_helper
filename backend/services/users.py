from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.auth.dev_session import is_admin_principal_name
from backend.contracts_users import UserCreateCommand, UserPatch
from backend.models_finance import Account, Entry, User
from backend.schemas_finance import UserRead
from backend.services.crud_policy import PolicyViolation, assert_unique_name, normalize_required_name

if TYPE_CHECKING:
    from backend.auth.contracts import RequestPrincipal


def normalize_user_name(name: str) -> str:
    return " ".join(name.split()).strip()


def _is_admin_principal(principal: RequestPrincipal) -> bool:
    return principal.is_admin


def find_user_by_name(db: Session, name: str) -> User | None:
    normalized = normalize_user_name(name)
    if not normalized:
        return None
    return db.scalar(select(User).where(func.lower(User.name) == normalized.lower()))


def ensure_user_by_name(
    db: Session,
    name: str,
    *,
    is_admin: bool = False,
) -> User:
    normalized = normalize_user_name(name)
    if not normalized:
        raise ValueError("User name cannot be empty")

    existing = find_user_by_name(db, normalized)
    if existing is not None:
        if is_admin and not existing.is_admin:
            existing.is_admin = True
            db.add(existing)
            db.flush()
        return existing

    user = User(name=normalized, is_admin=is_admin)
    db.add(user)
    db.flush()
    return user


def ensure_current_user(
    db: Session,
    current_user_name: str,
    *,
    is_admin: bool | None = None,
) -> User:
    return ensure_user_by_name(
        db,
        current_user_name,
        is_admin=is_admin_principal_name(current_user_name) if is_admin is None else is_admin,
    )


def create_user_with_unique_name(
    db: Session,
    *,
    raw_name: str,
    is_admin: bool = False,
) -> User:
    normalized_name = normalize_required_name(
        raw_name,
        normalizer=normalize_user_name,
        empty_detail="User name cannot be empty",
    )
    existing = find_user_by_name(db, normalized_name)
    assert_unique_name(
        existing_id=existing.id if existing is not None else None,
        current_id=None,
        conflict_detail="User already exists",
    )

    user = User(name=normalized_name, is_admin=is_admin)
    db.add(user)
    db.flush()
    return user


def _count_owned_resources(db: Session, *, user_id: str) -> tuple[int, int]:
    account_count = int(
        db.scalar(
            select(func.count(Account.id)).where(Account.owner_user_id == user_id)
        )
        or 0
    )
    entry_count = int(
        db.scalar(
            select(func.count(Entry.id)).where(
                Entry.owner_user_id == user_id,
                Entry.is_deleted.is_(False),
            )
        )
        or 0
    )
    return account_count, entry_count


def _to_user_read(
    *,
    user: User,
    principal_name: str,
    account_count: int,
    entry_count: int,
) -> UserRead:
    return UserRead(
        id=user.id,
        name=user.name,
        is_admin=user.is_admin,
        is_current_user=user.name.lower() == principal_name.lower(),
        account_count=account_count,
        entry_count=entry_count,
    )


def build_user_read(
    db: Session,
    *,
    user: User,
    principal_name: str,
) -> UserRead:
    account_count, entry_count = _count_owned_resources(db, user_id=user.id)
    return _to_user_read(
        user=user,
        principal_name=principal_name,
        account_count=account_count,
        entry_count=entry_count,
    )


def list_user_reads(
    db: Session,
    *,
    principal: RequestPrincipal,
) -> list[UserRead]:
    from backend.services.access_scope import load_user_for_principal

    if not _is_admin_principal(principal):
        user = load_user_for_principal(db, user_id=principal.user_id, principal=principal)
        return [build_user_read(db, user=user, principal_name=principal.user_name)]

    account_count_subquery = (
        select(func.count(Account.id))
        .where(Account.owner_user_id == User.id)
        .scalar_subquery()
    )
    entry_count_subquery = (
        select(func.count(Entry.id))
        .where(
            Entry.is_deleted.is_(False),
            Entry.owner_user_id == User.id,
        )
        .scalar_subquery()
    )

    rows = db.execute(
        select(
            User,
            account_count_subquery.label("account_count"),
            entry_count_subquery.label("entry_count"),
        ).order_by(func.lower(User.name).asc())
    ).all()
    return [
        _to_user_read(
            user=user,
            principal_name=principal.user_name,
            account_count=int(account_count or 0),
            entry_count=int(entry_count or 0),
        )
        for user, account_count, entry_count in rows
    ]


def rename_user_and_sync_entry_owner_labels(
    db: Session,
    *,
    user: User,
    raw_name: str,
) -> User:
    normalized_name = normalize_required_name(
        raw_name,
        normalizer=normalize_user_name,
        empty_detail="User name cannot be empty",
    )
    existing = find_user_by_name(db, normalized_name)
    assert_unique_name(
        existing_id=existing.id if existing is not None else None,
        current_id=user.id,
        conflict_detail="User already exists",
    )
    user.name = normalized_name
    db.execute(update(Entry).where(Entry.owner_user_id == user.id).values(owner=normalized_name))
    db.add(user)
    db.flush()
    return user


def create_user_for_principal(
    db: Session,
    *,
    command: UserCreateCommand,
    principal: RequestPrincipal,
) -> User:
    if not _is_admin_principal(principal):
        raise PolicyViolation.forbidden("Only admin principal can create users.")
    return create_user_with_unique_name(db, raw_name=command.name, is_admin=False)


def update_user_for_principal(
    db: Session,
    *,
    user_id: str,
    patch: UserPatch,
    principal: RequestPrincipal,
) -> User:
    from backend.services.access_scope import load_user_for_principal

    user = load_user_for_principal(db, user_id=user_id, principal=principal)
    if "name" in patch.model_fields_set and patch.name is not None:
        rename_user_and_sync_entry_owner_labels(
            db,
            user=user,
            raw_name=patch.name,
        )
    return user
