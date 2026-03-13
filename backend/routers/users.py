# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `users` routes.
# - Inputs: callers that import `backend/routers/users.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `users`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.contracts_users import UserPasswordChangeCommand
from backend.database import get_db
from backend.schemas_auth import UserPasswordChange
from backend.schemas_finance import UserRead
from backend.services.users import (
    change_password_for_current_user,
    list_user_reads,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[UserRead]:
    return list_user_reads(db, principal=principal)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: UserPasswordChange,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    change_password_for_current_user(
        db,
        user_id=principal.user_id,
        command=UserPasswordChangeCommand.model_validate(payload.model_dump()),
    )
    db.commit()
