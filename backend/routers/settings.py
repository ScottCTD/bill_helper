# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `settings` routes.
# - Inputs: callers that import `backend/routers/settings.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `settings`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal, require_admin_principal
from backend.database import get_db
from backend.schemas_settings import RuntimeSettingsRead, RuntimeSettingsUpdate
from backend.services.runtime_settings import build_runtime_settings_view, update_runtime_settings_override
from backend.services.runtime_settings_contracts import RuntimeSettingsPatch

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=RuntimeSettingsRead)
def get_runtime_settings(
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(get_current_principal),
) -> RuntimeSettingsRead:
    view = build_runtime_settings_view(db)
    return RuntimeSettingsRead.model_validate(view, from_attributes=True)


@router.patch("", response_model=RuntimeSettingsRead)
def patch_runtime_settings(
    payload: RuntimeSettingsUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> RuntimeSettingsRead:
    if payload.model_fields_set:
        update_runtime_settings_override(
            db,
            RuntimeSettingsPatch.model_validate(payload.model_dump(exclude_unset=True)),
        )
        db.commit()
    view = build_runtime_settings_view(db)
    return RuntimeSettingsRead.model_validate(view, from_attributes=True)
