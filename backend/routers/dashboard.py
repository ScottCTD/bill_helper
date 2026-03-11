from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal
from backend.database import get_db
from backend.schemas_finance import DashboardRead, DashboardTimelineRead
from backend.services.finance import (
    build_dashboard_read,
    build_dashboard_timeline_read,
    month_window,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardRead)
def get_dashboard(
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m"), pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> DashboardRead:
    try:
        month_window(month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must be in YYYY-MM format") from exc
    payload = build_dashboard_read(db, month=month, principal=principal)
    db.commit()
    return payload


@router.get("/timeline", response_model=DashboardTimelineRead)
def get_dashboard_timeline(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> DashboardTimelineRead:
    payload = build_dashboard_timeline_read(db, principal=principal)
    db.commit()
    return payload
