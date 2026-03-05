from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import build_engine, build_session_maker
from backend.db_meta import Base
from backend.enums_finance import EntryKind
from backend.models_finance import Account, Entry
from backend.services.entities import ensure_entity_by_name
from backend.services.entries import normalize_tag_name, set_entry_tags
from backend.services.groups import assign_initial_group
from backend.services.bootstrap import (
    run_schema_seed_and_stamp,
    stamp_alembic_head_for_database_url,
)
from backend.services.taxonomy_constants import (
    TAG_TYPE_SUBJECT_TYPE,
    TAG_TYPE_TAXONOMY_KEY,
)
from backend.services.taxonomy import assign_single_term_by_name
from backend.services.users import ensure_user_by_name
SUPPORTED_CURRENCIES = ("CAD", "USD", "CNY")
DEFAULT_ENTRY_CURRENCY = "CAD"


@dataclass(slots=True)
class SeedDemoResult:
    debit_account_name: str
    credit_account_name: str
    imported_row_count: int


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split()).strip()


def _title_case(value: str) -> str:
    return _normalize_whitespace(value).title()


def _parse_amount_minor(value: str) -> int:
    try:
        decimal_value = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount value: {value}") from exc
    minor = (abs(decimal_value) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor)


def _parse_kind(transaction_type: str) -> EntryKind:
    normalized = _normalize_whitespace(transaction_type).lower()
    return EntryKind.INCOME if normalized == "credit" else EntryKind.EXPENSE


def _normalize_tag_value(value: str) -> str:
    return _normalize_whitespace(value).lower()


def _extract_location_name(sub_description: str) -> str | None:
    cleaned = _normalize_whitespace(sub_description)
    if not cleaned:
        return None
    location_only = cleaned.split("(")[0].strip()
    if not location_only:
        return None
    parts = location_only.split()
    if len(parts) < 2:
        return None
    province = parts[-1]
    city_parts = parts[:-1]
    if len(province) != 2 or not province.isalpha():
        return None
    if any(re.fullmatch(r"[A-Za-z]+", part) is None for part in city_parts):
        return None
    return _normalize_tag_value(f"{' '.join(city_parts)} {province}")


def _derive_tags(
    description: str,
    sub_description: str,
    transaction_type: str,
) -> dict[str, str]:
    tags: dict[str, str] = {}
    type_tag = _normalize_tag_value(transaction_type)
    if type_tag:
        tags[type_tag] = "transaction_type"

    is_payment_from = description.lower().startswith("payment from")
    merchant_tag = _normalize_tag_value(description)
    if merchant_tag and not is_payment_from:
        tags[merchant_tag] = "merchant"

    if "apple pay" in sub_description.lower():
        tags["apple pay"] = "channel"

    location_tag = _extract_location_name(sub_description)
    if location_tag:
        tags[location_tag] = "location"

    if is_payment_from:
        tags["card payment"] = "payment"

    return tags


def _resolve_counterparty(
    db: Session,
    *,
    description: str,
    debit_account_entity_name: str,
    kind: EntryKind,
):
    lowered = description.lower()
    if kind == EntryKind.INCOME and lowered.startswith("payment from"):
        return ensure_entity_by_name(db, debit_account_entity_name, category="account")
    return ensure_entity_by_name(db, _title_case(description), category="merchant")


def _iter_credit_rows(csv_path: str) -> list[dict[str, str]]:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized_row = {str(key): str(value or "").strip() for key, value in row.items()}
            if not normalized_row.get("Date") or not normalized_row.get("Description"):
                continue
            rows.append(normalized_row)
        return rows


def _seed_demo_rows(
    db: Session,
    *,
    credit_rows: list[dict[str, str]],
) -> SeedDemoResult:
    existing_accounts = db.scalars(select(Account)).all()
    if existing_accounts:
        raise RuntimeError("Database reset failed: accounts still present after drop/create.")

    default_user = ensure_user_by_name(db, "admin")

    debit_entity = ensure_entity_by_name(db, "Demo Debit", category="account")
    credit_entity = ensure_entity_by_name(db, "Demo Credit", category="account")

    debit_account = Account(
        owner_user_id=default_user.id,
        entity_id=debit_entity.id,
        name=debit_entity.name,
        currency_code=DEFAULT_ENTRY_CURRENCY,
        is_active=True,
    )
    credit_account = Account(
        owner_user_id=default_user.id,
        entity_id=credit_entity.id,
        name=credit_entity.name,
        currency_code=DEFAULT_ENTRY_CURRENCY,
        is_active=True,
    )
    db.add_all([debit_account, credit_account])
    db.flush()

    for row in credit_rows:
        description = _normalize_whitespace(row.get("Description", ""))
        sub_description = _normalize_whitespace(row.get("Sub-description", ""))
        kind = _parse_kind(row.get("Type of Transaction", ""))
        counterparty = _resolve_counterparty(
            db,
            description=description,
            debit_account_entity_name=debit_account.name,
            kind=kind,
        )

        from_entity = credit_entity
        to_entity = counterparty
        if kind == EntryKind.INCOME:
            from_entity = counterparty
            to_entity = credit_entity

        entry = Entry(
            account_id=credit_account.id,
            group_id="",
            kind=kind,
            occurred_at=date.fromisoformat(row["Date"]),
            name=_title_case(description),
            amount_minor=_parse_amount_minor(row.get("Amount", "0")),
            currency_code=DEFAULT_ENTRY_CURRENCY,
            from_entity_id=from_entity.id,
            to_entity_id=to_entity.id,
            owner_user_id=default_user.id,
            from_entity=from_entity.name,
            to_entity=to_entity.name,
            owner=default_user.name,
            markdown_body=(
                f"Imported from statement CSV. "
                f"Sub-description: {sub_description or '(none)'}; "
                f"source_type={_normalize_whitespace(row.get('Type of Transaction', '')) or '(unknown)'}."
            ),
        )
        db.add(entry)
        assign_initial_group(db, entry)
        tag_types = _derive_tags(
            description=description,
            sub_description=sub_description,
            transaction_type=row.get("Type of Transaction", ""),
        )
        set_entry_tags(
            db,
            entry,
            list(tag_types.keys()),
        )
        for tag in entry.tags:
            tag_type = tag_types.get(normalize_tag_name(tag.name))
            if not tag_type:
                continue
            assign_single_term_by_name(
                db,
                taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
                subject_type=TAG_TYPE_SUBJECT_TYPE,
                subject_id=tag.id,
                term_name=tag_type,
            )

    db.commit()
    return SeedDemoResult(
        debit_account_name=debit_account.name,
        credit_account_name=credit_account.name,
        imported_row_count=len(credit_rows),
    )


def seed(csv_path: str) -> None:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Credit CSV not found at {csv_path}. "
            "Pass the CSV path as a positional argument or set BILL_HELPER_SEED_CREDIT_CSV."
        )
    credit_rows = _iter_credit_rows(csv_path)

    engine = build_engine()
    make_session = build_session_maker(engine)
    database_url = str(engine.url)
    result = run_schema_seed_and_stamp(
        engine=engine,
        metadata=Base.metadata,
        make_session=make_session,
        seed=lambda db: _seed_demo_rows(db, credit_rows=credit_rows),
        recreate_schema=True,
        stamp=lambda: stamp_alembic_head_for_database_url(database_url=database_url),
    )

    print(
        "Database reseeded. "
        f"Accounts: {result.debit_account_name}, {result.credit_account_name}. "
        f"Currencies configured: {', '.join(SUPPORTED_CURRENCIES)}. "
        f"Imported {result.imported_row_count} entries from {csv_path}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Reseed demo database from a credit-card CSV export.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=os.getenv("BILL_HELPER_SEED_CREDIT_CSV"),
        help="Path to the credit-card CSV file (or set BILL_HELPER_SEED_CREDIT_CSV).",
    )
    args = parser.parse_args()
    if not args.csv_path:
        parser.error(
            "CSV path is required. Pass it as a positional argument or set BILL_HELPER_SEED_CREDIT_CSV."
        )
    seed(args.csv_path)


if __name__ == "__main__":
    main()
