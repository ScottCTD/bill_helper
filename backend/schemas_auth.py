# CALLING SPEC:
# - Purpose: provide the `schemas_auth` module.
# - Inputs: callers that import `backend/schemas_auth.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `schemas_auth`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.contracts_users import (
    UserCreateCommand,
    UserPasswordChangeCommand,
    UserPasswordResetCommand,
    UserPatch,
)


class AuthSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthUserRead(AuthSchema):
    id: str
    name: str
    is_admin: bool = False

    model_config = ConfigDict(from_attributes=True)


class AuthSessionRead(AuthSchema):
    user: AuthUserRead
    session_id: str | None = None
    is_admin_impersonation: bool = False


class AuthLoginRequest(AuthSchema):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class AuthLoginResponse(AuthSessionRead):
    token: str


class AdminSessionRead(AuthSchema):
    id: str
    user_id: str
    user_name: str
    is_admin: bool = False
    is_admin_impersonation: bool = False
    created_at: datetime
    expires_at: datetime | None = None
    is_current: bool = False


class AdminUserCreate(UserCreateCommand):
    pass


class AdminUserUpdate(UserPatch):
    pass


class AdminUserPasswordReset(UserPasswordResetCommand):
    pass


class UserPasswordChange(UserPasswordChangeCommand):
    pass
