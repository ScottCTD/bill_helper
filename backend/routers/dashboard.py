from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account
from backend.schemas import DashboardRead
from backend.services.finance import (
    build_dashboard_analytics,
    build_reconciliation,
    month_window,
)
from backend.services.runtime_settings import resolve_runtime_settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardRead)
def get_dashboard(
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m"), pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
) -> DashboardRead:
    try:
        start, end = month_window(month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must be in YYYY-MM format") from exc

    runtime_settings = resolve_runtime_settings(db)
    dashboard_currency_code = runtime_settings.dashboard_currency_code

    analytics = build_dashboard_analytics(
        db,
        start=start,
        end=end,
        currency_code=dashboard_currency_code,
    )

    as_of = min(date.today(), end - timedelta(days=1))
    accounts = list(
        db.scalars(
            select(Account)
            .where(
                Account.is_active.is_(True),
                Account.currency_code == dashboard_currency_code,
            )
            .order_by(Account.name.asc())
        )
    )
    reconciliation = [build_reconciliation(db, account, as_of) for account in accounts]

    return DashboardRead(
        month=month,
        currency_code=dashboard_currency_code,
        **analytics,
        reconciliation=reconciliation,
    )
