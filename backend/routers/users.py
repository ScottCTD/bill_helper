from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal, get_current_principal
from backend.database import get_db
from backend.models_finance import Account, Entry, User
from backend.schemas_finance import UserCreate, UserRead, UserUpdate
from backend.services.access_scope import (
    get_user_for_principal_or_404,
    is_admin_principal,
)
from backend.services.crud_policy import (
    PolicyViolation,
    translate_policy_violation,
)
from backend.services.users import (
    create_user_with_unique_name,
    rename_user_and_sync_entry_owner_labels,
)

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
def list_users(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[UserRead]:
    if not is_admin_principal(principal):
        user = get_user_for_principal_or_404(db, user_id=principal.user_id, principal=principal)
        account_count = int(
            db.scalar(select(func.count(Account.id)).where(Account.owner_user_id == user.id)) or 0
        )
        entry_count = int(
            db.scalar(
                select(func.count(Entry.id)).where(
                    Entry.owner_user_id == user.id,
                    Entry.is_deleted.is_(False),
                )
            )
            or 0
        )
        return [
            _to_schema(
                user,
                principal.user_name,
                account_count=account_count,
                entry_count=entry_count,
            )
        ]

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
            principal.user_name,
            account_count=int(account_count or 0),
            entry_count=int(entry_count or 0),
        )
        for user, account_count, entry_count in rows
    ]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> UserRead:
    if not is_admin_principal(principal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin principal can create users.",
        )

    try:
        user = create_user_with_unique_name(db, raw_name=payload.name)
    except PolicyViolation as exc:
        raise translate_policy_violation(exc) from exc

    db.commit()
    db.refresh(user)

    return _to_schema(user, principal.user_name, account_count=0, entry_count=0)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> UserRead:
    user = get_user_for_principal_or_404(db, user_id=user_id, principal=principal)

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data:
        try:
            rename_user_and_sync_entry_owner_labels(
                db,
                user=user,
                raw_name=update_data["name"],
            )
        except PolicyViolation as exc:
            raise translate_policy_violation(exc) from exc
    db.commit()
    db.refresh(user)

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
    return _to_schema(user, principal.user_name, account_count=account_count, entry_count=entry_count)
