from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal, get_current_principal, require_admin_principal
from backend.database import get_db
from backend.schemas_finance import UserCreate, UserRead, UserUpdate
from backend.services.crud_policy import (
    PolicyViolation,
    translate_policy_violation,
)
from backend.services.users import (
    build_user_read,
    create_user_for_principal,
    list_user_reads,
    update_user_for_principal,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[UserRead]:
    return list_user_reads(db, principal=principal)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> UserRead:
    try:
        user = create_user_for_principal(db, raw_name=payload.name, principal=principal)
    except PolicyViolation as exc:
        raise translate_policy_violation(exc) from exc

    db.commit()
    db.refresh(user)

    return build_user_read(db, user=user, principal_name=principal.user_name)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> UserRead:
    try:
        user = update_user_for_principal(
            db,
            user_id=user_id,
            raw_name=payload.name if "name" in payload.model_dump(exclude_unset=True) else None,
            principal=principal,
        )
    except PolicyViolation as exc:
        raise translate_policy_violation(exc) from exc
    db.commit()
    db.refresh(user)
    return build_user_read(db, user=user, principal_name=principal.user_name)
