from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal, get_current_principal
from backend.database import get_db
from backend.schemas_finance import DashboardRead
from backend.services.finance import (
    build_dashboard_read,
    month_window,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardRead)
def get_dashboard(
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m"), pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> DashboardRead:
    try:
        month_window(month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must be in YYYY-MM format") from exc
    return build_dashboard_read(db, month=month, principal=principal)
