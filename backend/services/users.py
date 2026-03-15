# CALLING SPEC:
# - Purpose: implement focused service logic for `users`.
# - Inputs: callers that import `backend/services/users.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `users`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.contracts_users import (
    UserCreateCommand,
    UserPasswordChangeCommand,
    UserPasswordResetCommand,
    UserPatch,
)
from backend.models_finance import Account, Entry, User
from backend.schemas_finance import UserRead
from backend.services.agent_workspace import ensure_user_workspace_provisioned, remove_user_workspace
from backend.services.crud_policy import PolicyViolation, assert_unique_name, normalize_required_name
from backend.services.passwords import PasswordVerificationResult, hash_password, verify_password
from backend.services.sessions import revoke_sessions_for_user
from backend.services.user_files import delete_user_file_root

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


def load_user_by_name(db: Session, name: str) -> User:
    user = find_user_by_name(db, name)
    if user is None:
        raise PolicyViolation.not_found("User not found")
    return user


def create_user_with_unique_name(
    db: Session,
    *,
    raw_name: str,
    password: str,
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

    user = User(
        name=normalized_name,
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    db.add(user)
    db.flush()
    ensure_user_workspace_provisioned(user_id=user.id)
    return user


def create_or_reset_admin_user(
    db: Session,
    *,
    raw_name: str,
    password: str,
) -> User:
    existing = find_user_by_name(db, raw_name)
    if existing is None:
        return create_user_with_unique_name(
            db,
            raw_name=raw_name,
            password=password,
            is_admin=True,
        )

    existing.password_hash = hash_password(password)
    existing.is_admin = True
    db.add(existing)
    db.flush()
    ensure_user_workspace_provisioned(user_id=existing.id)
    return existing


def authenticate_user(
    db: Session,
    *,
    username: str,
    password: str,
) -> tuple[User, PasswordVerificationResult]:
    user = load_user_by_name(db, username)
    result = verify_password(user.password_hash, password)
    if not result.is_valid:
        if result.requires_reset:
            raise PolicyViolation.forbidden("Password reset is required for this user.")
        raise PolicyViolation.forbidden("Invalid username or password.")
    if result.needs_rehash:
        user.password_hash = hash_password(password)
        db.add(user)
        db.flush()
    return user, result


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
    principal_user_id: str,
    account_count: int,
    entry_count: int,
) -> UserRead:
    return UserRead(
        id=user.id,
        name=user.name,
        is_admin=user.is_admin,
        is_current_user=user.id == principal_user_id,
        account_count=account_count,
        entry_count=entry_count,
    )


def build_user_read(
    db: Session,
    *,
    user: User,
    principal_user_id: str,
) -> UserRead:
    account_count, entry_count = _count_owned_resources(db, user_id=user.id)
    return _to_user_read(
        user=user,
        principal_user_id=principal_user_id,
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
        return [build_user_read(db, user=user, principal_user_id=principal.user_id)]

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
            principal_user_id=principal.user_id,
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


def create_user_for_admin(
    db: Session,
    *,
    command: UserCreateCommand,
    principal: RequestPrincipal,
) -> User:
    if not _is_admin_principal(principal):
        raise PolicyViolation.forbidden("Only admin principal can create users.")
    return create_user_with_unique_name(
        db,
        raw_name=command.name,
        password=command.password,
        is_admin=command.is_admin,
    )


def update_user_for_admin(
    db: Session,
    *,
    user_id: str,
    patch: UserPatch,
    principal: RequestPrincipal,
) -> User:
    from backend.services.access_scope import load_user_for_principal

    if not _is_admin_principal(principal):
        raise PolicyViolation.forbidden("Only admin principal can update users.")

    user = load_user_for_principal(db, user_id=user_id, principal=principal)
    if "name" in patch.model_fields_set and patch.name is not None:
        rename_user_and_sync_entry_owner_labels(
            db,
            user=user,
            raw_name=patch.name,
        )
    if "is_admin" in patch.model_fields_set and patch.is_admin is not None:
        user.is_admin = patch.is_admin
        db.add(user)
        db.flush()
    return user


def reset_user_password_for_admin(
    db: Session,
    *,
    user_id: str,
    command: UserPasswordResetCommand,
    principal: RequestPrincipal,
) -> User:
    from backend.services.access_scope import load_user_for_principal

    if not _is_admin_principal(principal):
        raise PolicyViolation.forbidden("Only admin principal can reset passwords.")

    user = load_user_for_principal(db, user_id=user_id, principal=principal)
    user.password_hash = hash_password(command.new_password)
    db.add(user)
    db.flush()
    return user


def change_password_for_current_user(
    db: Session,
    *,
    user_id: str,
    command: UserPasswordChangeCommand,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise PolicyViolation.not_found("User not found")
    result = verify_password(user.password_hash, command.current_password)
    if not result.is_valid:
        if result.requires_reset:
            raise PolicyViolation.forbidden("Password reset is required for this user.")
        raise PolicyViolation.forbidden("Current password is incorrect.")
    user.password_hash = hash_password(command.new_password)
    db.add(user)
    db.flush()
    return user


def delete_user_for_admin(
    db: Session,
    *,
    user_id: str,
    principal: RequestPrincipal,
) -> None:
    from backend.services.access_scope import load_user_for_principal

    if not _is_admin_principal(principal):
        raise PolicyViolation.forbidden("Only admin principal can delete users.")
    user = load_user_for_principal(db, user_id=user_id, principal=principal)
    remove_user_workspace(user_id=user.id)
    delete_user_file_root(user_id=user.id)
    revoke_sessions_for_user(db, user_id=user.id)
    db.delete(user)
    db.flush()
