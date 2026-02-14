from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account, Entry, User
from backend.schemas import UserCreate, UserRead, UserUpdate
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.users import ensure_current_user, find_user_by_name, normalize_user_name

router = APIRouter(prefix="/users", tags=["users"])


def _to_schema(
    user: User,
    current_user_name: str,
    *,
    account_count: int | None = None,
    entry_count: int | None = None,
) -> UserRead:
    return UserRead(
        id=user.id,
        name=user.name,
        is_current_user=user.name.lower() == current_user_name.lower(),
        account_count=account_count,
        entry_count=entry_count,
    )


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    settings = resolve_runtime_settings(db)
    ensure_current_user(db, settings.current_user_name)
    db.commit()

    account_count_subquery = (
        select(func.count(Account.id))
        .where(
            Account.owner_user_id == User.id,
        )
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
        _to_schema(
            user,
            settings.current_user_name,
            account_count=int(account_count or 0),
            entry_count=int(entry_count or 0),
        )
        for user, account_count, entry_count in rows
    ]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    normalized_name = normalize_user_name(payload.name)
    if not normalized_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User name cannot be empty")

    existing = find_user_by_name(db, normalized_name)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = User(name=normalized_name)
    db.add(user)
    db.commit()
    db.refresh(user)

    settings = resolve_runtime_settings(db)
    return _to_schema(user, settings.current_user_name, account_count=0, entry_count=0)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db)) -> UserRead:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data:
        normalized_name = normalize_user_name(update_data["name"] or "")
        if not normalized_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User name cannot be empty")

        existing = find_user_by_name(db, normalized_name)
        if existing is not None and existing.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

        user.name = normalized_name
        db.execute(update(Entry).where(Entry.owner_user_id == user.id).values(owner=normalized_name))

    db.add(user)
    db.commit()
    db.refresh(user)

    settings = resolve_runtime_settings(db)
    account_count = int(db.scalar(select(func.count(Account.id)).where(Account.owner_user_id == user.id)) or 0)
    entry_count = int(
        db.scalar(
            select(func.count(Entry.id)).where(
                Entry.owner_user_id == user.id,
                Entry.is_deleted.is_(False),
            )
        )
        or 0
    )
    return _to_schema(user, settings.current_user_name, account_count=account_count, entry_count=entry_count)
