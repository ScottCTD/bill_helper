from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.models_finance import Entry
from backend.schemas_finance import CurrencyRead
from backend.services.access_scope import entry_owner_filter

router = APIRouter(prefix="/currencies", tags=["currencies"])

DEFAULT_CURRENCIES: dict[str, str] = {
    "CAD": "Canadian Dollar",
    "USD": "US Dollar",
    "CNY": "Chinese Yuan",
}


@router.get("", response_model=list[CurrencyRead])
def list_currencies(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[CurrencyRead]:
    rows = db.execute(
        select(
            Entry.currency_code,
            func.count(Entry.id).label("entry_count"),
        )
        .where(
            Entry.is_deleted.is_(False),
            entry_owner_filter(principal),
        )
        .group_by(Entry.currency_code)
        .order_by(Entry.currency_code.asc())
    ).all()
    entry_counts = {str(code).upper(): int(count or 0) for code, count in rows}

    all_codes = sorted({*DEFAULT_CURRENCIES.keys(), *entry_counts.keys()})
    return [
        CurrencyRead(
            code=code,
            name=DEFAULT_CURRENCIES.get(code, code),
            entry_count=entry_counts.get(code, 0),
            is_placeholder=code not in DEFAULT_CURRENCIES,
        )
        for code in all_codes
    ]
