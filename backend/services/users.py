from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.models_finance import Entry, User
from backend.services.crud_policy import assert_unique_name, normalize_required_name


def normalize_user_name(name: str) -> str:
    return " ".join(name.split()).strip()


def find_user_by_name(db: Session, name: str) -> User | None:
    normalized = normalize_user_name(name)
    if not normalized:
        return None
    return db.scalar(select(User).where(func.lower(User.name) == normalized.lower()))


def ensure_user_by_name(db: Session, name: str) -> User:
    normalized = normalize_user_name(name)
    if not normalized:
        raise ValueError("User name cannot be empty")

    existing = find_user_by_name(db, normalized)
    if existing is not None:
        return existing

    user = User(name=normalized)
    db.add(user)
    db.flush()
    return user


def ensure_current_user(db: Session, current_user_name: str) -> User:
    return ensure_user_by_name(db, current_user_name)


def create_user_with_unique_name(db: Session, *, raw_name: str) -> User:
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

    user = User(name=normalized_name)
    db.add(user)
    db.flush()
    return user


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
