from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import RuntimeSettingsRead, RuntimeSettingsUpdate
from backend.services.runtime_settings import build_runtime_settings_read, update_runtime_settings_override

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=RuntimeSettingsRead)
def get_runtime_settings(db: Session = Depends(get_db)) -> RuntimeSettingsRead:
    return build_runtime_settings_read(db)


@router.patch("", response_model=RuntimeSettingsRead)
def patch_runtime_settings(payload: RuntimeSettingsUpdate, db: Session = Depends(get_db)) -> RuntimeSettingsRead:
    update_data = payload.model_dump(exclude_unset=True)
    if update_data:
        update_runtime_settings_override(db, update_data)
        db.commit()
    return build_runtime_settings_read(db)
