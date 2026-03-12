from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, joinedload

from backend.models_finance import User, UserSession


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(
    db: Session,
    *,
    user: User,
    is_admin_impersonation: bool = False,
    expires_at: datetime | None = None,
) -> tuple[str, UserSession]:
    token = secrets.token_urlsafe(32)
    session_row = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=expires_at,
        is_admin_impersonation=is_admin_impersonation,
    )
    db.add(session_row)
    db.flush()
    return token, session_row


def _prune_expired_session(db: Session, session_row: UserSession) -> None:
    db.delete(session_row)
    db.flush()


def is_session_expired(session_row: UserSession) -> bool:
    return session_row.expires_at is not None and session_row.expires_at <= utc_now()


def load_session_by_token(db: Session, *, token: str) -> UserSession | None:
    session_row = db.scalar(
        select(UserSession)
        .where(UserSession.token_hash == hash_session_token(token))
        .options(joinedload(UserSession.user))
    )
    if session_row is None:
        return None
    if is_session_expired(session_row):
        _prune_expired_session(db, session_row)
        return None
    return session_row


def list_active_sessions(db: Session) -> list[UserSession]:
    rows = list(
        db.scalars(
            select(UserSession)
            .where(
                or_(
                    UserSession.expires_at.is_(None),
                    UserSession.expires_at > utc_now(),
                )
            )
            .options(joinedload(UserSession.user))
            .order_by(UserSession.created_at.desc())
        )
    )
    return rows


def revoke_session_by_id(db: Session, *, session_id: str) -> bool:
    session_row = db.get(UserSession, session_id)
    if session_row is None:
        return False
    db.delete(session_row)
    db.flush()
    return True


def revoke_current_session(db: Session, *, session_id: str) -> bool:
    return revoke_session_by_id(db, session_id=session_id)


def revoke_sessions_for_user(db: Session, *, user_id: str) -> None:
    db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    db.flush()
