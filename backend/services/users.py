from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import User


def normalize_user_name(name: str) -> str:
    return " ".join(name.split()).strip()


def find_user_by_name(db: Session, name: str) -> User | None:
    normalized = normalize_user_name(name)
    if not normalized:
        return None
    return db.scalar(select(User).where(func.lower(User.name) == normalized.lower()))


def get_or_create_user(db: Session, name: str) -> User:
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
    return get_or_create_user(db, current_user_name)
