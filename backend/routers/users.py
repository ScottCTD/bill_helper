from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal, require_admin_principal
from backend.contracts_users import UserCreateCommand, UserPatch
from backend.database import get_db
from backend.schemas_finance import UserCreate, UserRead, UserUpdate
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
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> list[UserRead]:
    return list_user_reads(db, principal=principal)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> UserRead:
    user = create_user_for_principal(
        db,
        command=UserCreateCommand.model_validate(payload.model_dump()),
        principal=principal,
    )

    db.commit()
    db.refresh(user)

    return build_user_read(db, user=user, principal_name=principal.user_name)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> UserRead:
    user = update_user_for_principal(
        db,
        user_id=user_id,
        patch=UserPatch.model_validate(payload.model_dump(exclude_unset=True)),
        principal=principal,
    )
    db.commit()
    db.refresh(user)
    return build_user_read(db, user=user, principal_name=principal.user_name)
