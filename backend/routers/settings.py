from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal, require_admin_principal
from backend.database import get_db
from backend.schemas_finance import RuntimeSettingsRead, RuntimeSettingsUpdate
from backend.services.runtime_settings import build_runtime_settings_read, update_runtime_settings_override

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=RuntimeSettingsRead)
def get_runtime_settings(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> RuntimeSettingsRead:
    return build_runtime_settings_read(db, principal_name=principal.user_name)


@router.patch("", response_model=RuntimeSettingsRead)
def patch_runtime_settings(
    payload: RuntimeSettingsUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> RuntimeSettingsRead:
    if payload.model_fields_set:
        update_runtime_settings_override(db, payload)
        db.commit()
    return build_runtime_settings_read(db, principal_name=principal.user_name)
