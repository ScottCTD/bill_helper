from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.contracts_users import (
    UserCreateCommand,
    UserPasswordChangeCommand,
    UserPasswordResetCommand,
    UserPatch,
)


class AuthUserRead(BaseModel):
    id: str
    name: str
    is_admin: bool = False

    model_config = ConfigDict(from_attributes=True)


class AuthSessionRead(BaseModel):
    user: AuthUserRead
    session_id: str | None = None
    is_admin_impersonation: bool = False


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class AuthLoginResponse(AuthSessionRead):
    token: str


class AdminSessionRead(BaseModel):
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
