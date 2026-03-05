"""Seed a database with the default tags, entity categories, and accounts.

Can be used standalone to reset the local DB or imported by other scripts.

Usage:
    uv run python scripts/seed_defaults.py          # reset local DB
    uv run python scripts/seed_defaults.py --help
"""

from __future__ import annotations

import argparse
import logging
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import build_engine_for_url, build_session_maker

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.models_finance import Account, Tag, TaxonomyTerm, User

# ---------------------------------------------------------------------------
# Default data
# ---------------------------------------------------------------------------

DEFAULT_TAGS: list[dict[str, str]] = [
    {"name": "housing", "type": "expense", "description": "Rent, mortgage payments, condo/HOA fees, and other core housing payments."},
    {"name": "home_maintenance", "type": "expense", "description": "Home repairs, contractors, renovations, and maintenance services."},
    {"name": "utilities", "type": "expense", "description": "Electricity, gas, water, trash, heating, and other utility bills."},
    {"name": "internet_mobile", "type": "expense", "description": "Internet service, mobile phone plans, and related connectivity charges."},

    {"name": "grocery", "type": "expense", "description": "Food and household staples from grocery stores and supermarkets."},
    {"name": "dining_out", "type": "expense", "description": "Restaurants, takeout, delivery, and prepared meals purchased to eat."},
    {"name": "coffee_snacks", "type": "expense", "description": "Coffee shops, bubble tea, desserts, snacks, and small convenience food purchases."},
    {"name": "alcohol_bars", "type": "expense", "description": "Bars, pubs, alcohol purchases, and related nightlife spending."},

    {"name": "shopping", "type": "expense", "description": "General retail and online purchases that do not fit a more specific tag (clothing, electronics, home_furnishings, etc.). Do not combine with those specific tags."},
    {"name": "clothing", "type": "expense", "description": "Clothing, shoes, accessories, and related apparel purchases."},
    {"name": "electronics", "type": "expense", "description": "Electronics, gadgets, computers, phones, and related accessories."},
    {"name": "home", "type": "expense", "description": "Furniture, decor, household supplies, and other home-related purchases (excluding maintenance/repairs and core housing payments)."},

    {"name": "personal_care", "type": "expense", "description": "Haircuts, grooming, cosmetics, toiletries, and personal care services."},
    {"name": "health_medical", "type": "expense", "description": "Doctor visits, dental, vision, clinics, tests, and other medical services."},
    {"name": "pharmacy", "type": "expense", "description": "Prescriptions and over-the-counter medication purchases at pharmacies."},
    {"name": "fitness", "type": "expense", "description": "Gym memberships, fitness classes, sports training, and fitness-related spending."},

    {"name": "transportation", "type": "expense", "description": "Public transit, rideshare, taxis, and other non-car transportation."},
    {"name": "fuel", "type": "expense", "description": "Gasoline, diesel, EV charging, and other vehicle energy costs."},
    {"name": "auto", "type": "expense", "description": "Car maintenance, repairs, parking, tolls, registration, and car-related costs excluding fuel and insurance."},

    {"name": "insurance", "type": "expense", "description": "Insurance premiums such as home, auto, life, travel, or other policies."},
    {"name": "travel", "type": "expense", "description": "Flights, hotels, bookings, and other trip-related spending."},
    {"name": "entertainment", "type": "expense", "description": "Movies, events, tickets, hobbies, and leisure activities."},
    {"name": "subscriptions", "type": "expense", "description": "Recurring subscriptions like streaming, software, apps, and memberships."},
    {"name": "education", "type": "expense", "description": "Tuition, courses, training, books, and education-related expenses."},
    {"name": "gifts", "type": "expense", "description": "Gifts given to others, including holidays and special occasions."},
    {"name": "donations_charity", "type": "expense", "description": "Charitable donations and other non-profit contributions."},
    {"name": "kids_childcare", "type": "expense", "description": "Childcare, kids activities, school-related costs, and child expenses."},
    {"name": "pets", "type": "expense", "description": "Pet food, vet visits, grooming, supplies, and pet services."},

    {"name": "taxes", "type": "expense", "description": "Income tax payments, property tax, installments, and other taxes paid."},
    {"name": "fees", "type": "expense", "description": "Bank fees, service charges, penalties, and miscellaneous fees."},
    {"name": "interest_expense", "type": "expense", "description": "Interest paid on credit cards, loans, lines of credit, or financing."},

    {"name": "salary_wages", "type": "income", "description": "Regular salary, wages, and payroll income."},
    {"name": "bonus", "type": "income", "description": "Bonuses, commissions, and other variable compensation."},
    {"name": "business_income", "type": "income", "description": "Self-employment, freelance, contract, or business revenue."},
    {"name": "interest_income", "type": "income", "description": "Interest earned from bank accounts, GICs, bonds, or lending."},
    {"name": "dividends", "type": "income", "description": "Dividend income from stocks, funds, or other investments."},
    {"name": "investment_gains", "type": "income", "description": "Realized gains from selling investments or assets."},
    {"name": "refund", "type": "income", "description": "Refunds for prior purchases, returns, chargebacks, or reimbursements treated as income."},
    {"name": "reimbursement", "type": "income", "description": "Repayments for expenses you covered (work, shared purchases, reimbursements)."},
    {"name": "gifts_received", "type": "income", "description": "Money received as gifts from others."},
    {"name": "other_income", "type": "income", "description": "Any income that does not fit the other income categories."},

    {"name": "internal_transfer", "type": "internal", "description": "Money moved between your own accounts (e.g., chequing to savings, paying your own credit card from chequing). Not income or expense."},
    {"name": "e_transfer", "type": "internal", "description": "Interac e-Transfer payment method marker (send/receive). Use alongside a purpose tag when known, or with needs_review when unknown."},
    {"name": "needs_review", "type": "internal", "description": "Purpose is unclear or classification is uncertain and needs manual follow-up."},
    {"name": "cash_withdrawal", "type": "internal", "description": "ATM and cash withdrawals used to obtain physical cash."},
    {"name": "debt_payment", "type": "internal", "description": "Payments toward credit cards, loans, or other debt principal/settlement movements."},
    {"name": "savings_investments", "type": "internal", "description": "Contributions or deposits into savings or investment accounts (movement, not spending)."},
    {"name": "uncategorized", "type": "internal", "description": "Fallback tag for transactions not yet classified."},
    {"name": "one_time", "type": "internal", "description": "Marks a transaction as irregular/non-recurring for reporting and budgeting."},
]

DEFAULT_ENTITY_CATEGORIES: list[dict[str, str]] = [
    {"name": "merchant", "description": "Default for businesses the user buys from (retail, restaurants, apps, online services, marketplaces, rideshare, etc.)"},
    {"name": "account", "description": "A specific account/instrument the user owns or manages (checking, credit card, prepaid card, transit card, loan). Use when the entity represents the account itself, not the bank."},
    {"name": "financial_institution", "description": "Banks, credit unions, brokerages, payment processors, card issuers (the institution, not the user's specific account)."},
    {"name": "government", "description": "Government bodies and agencies (tax authority, city/province/federal departments)."},
    {"name": "utility_provider", "description": "Providers of utilities and essential services (electricity, gas, water, telecom, internet)."},
    {"name": "employer", "description": "Organizations that pay the user compensation (salary, wages)."},
    {"name": "investment_entity", "description": "Investment counterparties not well-modeled as a merchant (funds, VC/PE firms, investment partnerships)."},
    {"name": "person", "description": "Individuals (friends/family/roommates) when the user wants a named counterparty."},
    {"name": "placeholder", "description": "Temporary/unknown entity used during ingestion or when the counterparty is unclear."},
    {"name": "organization", "description": "Catch-all for non-merchant orgs that aren't clearly government/financial/utility/employer (e.g., nonprofits, clubs, associations)."},
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_accounts(db: Session) -> tuple["User", "Account", "Account"]:
    """Create admin user and Scotiabank Debit/Credit accounts. Returns (user, debit_account, credit_account)."""
    from backend.models_finance import Account, Entity, User

    user = User(name="admin")
    db.add(user)
    db.flush()

    debit_entity = Entity(name="Scotiabank Debit", category="account")
    credit_entity = Entity(name="Scotiabank Credit", category="account")
    db.add_all([debit_entity, credit_entity])
    db.flush()

    debit_account = Account(
        owner_user_id=user.id,
        entity_id=debit_entity.id,
        name="Scotiabank Debit",
        currency_code="CAD",
        is_active=True,
    )
    credit_account = Account(
        owner_user_id=user.id,
        entity_id=credit_entity.id,
        name="Scotiabank Credit",
        currency_code="CAD",
        is_active=True,
    )
    db.add_all([debit_account, credit_account])
    db.flush()

    from backend.services.taxonomy import assign_single_term_by_name
    assign_single_term_by_name(db, taxonomy_key="entity_category", subject_type="entity", subject_id=debit_entity.id, term_name="account")
    assign_single_term_by_name(db, taxonomy_key="entity_category", subject_type="entity", subject_id=credit_entity.id, term_name="account")

    return user, debit_account, credit_account


def _tag_color(name: str) -> str:
    """Generate a deterministic HSL color from a tag name (mirrors frontend fallbackTagColor)."""
    h = 0
    for ch in name:
        h = ((h * 31) + ord(ch)) & 0xFFFFFFFF
    return f"hsl({h % 360} 62% 72%)"


def seed_tags(db: Session, tags: list[dict[str, str]] | None = None) -> list["Tag"]:
    """Create tags and assign tag_type taxonomy. Returns list of Tag objects."""
    from backend.models_finance import Tag
    from backend.services.taxonomy import assign_single_term_by_name

    tags = tags or DEFAULT_TAGS
    created = []
    for tag_data in tags:
        tag = Tag(
            name=tag_data["name"],
            color=_tag_color(tag_data["name"]),
            description=tag_data.get("description"),
        )
        db.add(tag)
        db.flush()
        assign_single_term_by_name(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_id=tag.id,
            term_name=tag_data["type"],
        )
        created.append(tag)
    return created


def seed_entity_categories(
    db: Session,
    categories: list[dict[str, str]] | None = None,
) -> list["TaxonomyTerm"]:
    """Create entity_category taxonomy terms with descriptions. Returns list of TaxonomyTerm objects."""
    from backend.services.taxonomy import ensure_term, get_taxonomy_by_key

    categories = categories or DEFAULT_ENTITY_CATEGORIES
    taxonomy = get_taxonomy_by_key(db, "entity_category")
    if taxonomy is None:
        raise RuntimeError("entity_category taxonomy not found")

    created = []
    for cat in categories:
        term = ensure_term(db, taxonomy=taxonomy, name=cat["name"])
        if cat.get("description"):
            term.metadata_json = {"description": cat["description"]}
            db.add(term)
        db.flush()
        created.append(term)
    return created


def seed_user_memory(
    db: Session,
    *,
    on_error: Literal["best_effort", "fail_fast"] = "best_effort",
) -> str | None:
    """Copy user_memory from the production DB into the given session's runtime_settings."""
    from backend.models_finance import RuntimeSettings

    from backend.config import get_settings

    prod_db_path = get_settings().data_dir / "bill_helper.db"
    if not prod_db_path.exists():
        return None

    prod_engine = build_engine_for_url(f"sqlite:///{prod_db_path}")
    prod_session = build_session_maker(prod_engine)()
    try:
        from sqlalchemy import select
        row = prod_session.scalar(
            select(RuntimeSettings).where(RuntimeSettings.scope == "default")
        )
        memory = row.user_memory if row else None
    except SQLAlchemyError as exc:
        if on_error == "fail_fast":
            raise RuntimeError(
                f"Failed to read user_memory from production DB at {prod_db_path}"
            ) from exc
        logger.warning(
            "seed_user_memory read failed; continuing best-effort. path=%s error_type=%s error=%s",
            prod_db_path,
            type(exc).__name__,
            str(exc),
        )
        memory = None
    finally:
        prod_session.close()
        prod_engine.dispose()

    if memory:
        settings = RuntimeSettings(scope="default", user_memory=memory)
        db.add(settings)
        db.flush()
    return memory


def seed_all(
    db: Session,
    *,
    include_user_memory: bool = False,
    user_memory_on_error: Literal["best_effort", "fail_fast"] = "best_effort",
) -> dict[str, Any]:
    """Run all seed functions. Returns a summary dict."""
    from backend.services.taxonomy import ensure_default_taxonomies

    ensure_default_taxonomies(db)
    user, debit, credit = seed_accounts(db)
    tags = seed_tags(db)
    entity_cats = seed_entity_categories(db)

    memory = None
    if include_user_memory:
        memory = seed_user_memory(db, on_error=user_memory_on_error)

    db.commit()
    return {
        "user": user.name,
        "accounts": [debit.name, credit.name],
        "tags": len(tags),
        "entity_categories": len(entity_cats),
        "user_memory": bool(memory),
    }


# ---------------------------------------------------------------------------
# Standalone: reset local DB
# ---------------------------------------------------------------------------

def reset_local_db() -> None:
    """Drop all tables, recreate, seed defaults, stamp Alembic."""
    import backend.models_agent  # noqa: F401
    import backend.models_finance  # noqa: F401
    from backend.db_meta import Base

    from backend.config import get_settings
    from backend.services.bootstrap import (
        run_schema_seed_and_stamp,
        stamp_alembic_head_for_sqlite_path,
    )

    settings = get_settings()
    db_path = settings.data_dir / "bill_helper.db"
    settings.ensure_data_dir()

    if db_path.exists():
        db_path.unlink()
        print(f"Removed {db_path}")

    engine = build_engine_for_url(f"sqlite:///{db_path}")
    make_session = build_session_maker(engine)
    result = run_schema_seed_and_stamp(
        engine=engine,
        metadata=Base.metadata,
        make_session=make_session,
        seed=seed_all,
        recreate_schema=False,
        stamp=lambda: stamp_alembic_head_for_sqlite_path(db_path),
    )

    print(f"Local DB reset at {db_path}")
    print(f"  User: {result['user']}")
    print(f"  Accounts: {', '.join(result['accounts'])}")
    print(f"  Tags: {result['tags']}")
    print(f"  Entity categories: {result['entity_categories']}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Reset local DB and seed defaults.")
    parser.parse_args()
    reset_local_db()


if __name__ == "__main__":
    main()
