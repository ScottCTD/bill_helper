from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database import build_engine
from backend.models_finance import Entity


def create_account(client, name: str = "Checking", *, headers: dict[str, str] | None = None) -> dict:
    response = client.post(
        "/api/v1/accounts",
        json={
            "name": name,
            "currency_code": "CAD",
            "is_active": True,
        },
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def create_entity(client, name: str, *, category: str | None = None) -> dict:
    payload = {"name": name}
    if category is not None:
        payload["category"] = category
    response = client.post("/api/v1/entities", json=payload)
    response.raise_for_status()
    return response.json()


def create_legacy_account_like_entity(name: str) -> None:
    with Session(build_engine()) as db:
        db.add(Entity(name=name, category="account"))
        db.commit()


def create_entry(
    client,
    account_id: str,
    kind: str,
    amount_minor: int,
    occurred_at: str,
    *,
    currency_code: str = "CAD",
    tags: list[str] | None = None,
    name: str | None = None,
    from_entity: str | None = None,
    to_entity: str | None = None,
    headers: dict[str, str] | None = None,
):
    response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": kind,
            "occurred_at": occurred_at,
            "name": name or f"{kind.lower()}-{occurred_at}",
            "amount_minor": amount_minor,
            "currency_code": currency_code,
            "from_entity": from_entity,
            "to_entity": to_entity,
            "tags": tags or [],
        },
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def test_reconciliation_math(client):
    account = create_account(client)

    opening_snapshot = client.post(
        f"/api/v1/accounts/{account['id']}/snapshots",
        json={"snapshot_at": "2026-01-01", "balance_minor": 500000, "note": "Opening balance"},
    )
    opening_snapshot.raise_for_status()
    closing_snapshot = client.post(
        f"/api/v1/accounts/{account['id']}/snapshots",
        json={"snapshot_at": "2026-02-01", "balance_minor": 420000, "note": "Month-end balance"},
    )
    closing_snapshot.raise_for_status()

    create_entry(client, account["id"], "EXPENSE", 70000, "2026-01-10")
    create_entry(client, account["id"], "INCOME", 10000, "2026-01-20")
    create_entry(client, account["id"], "EXPENSE", 5000, "2026-02-01", name="Statement-day coffee")
    create_entry(client, account["id"], "EXPENSE", 2000, "2026-02-10")

    reconciliation = client.get(
        f"/api/v1/accounts/{account['id']}/reconciliation", params={"as_of": "2026-02-15"}
    )
    reconciliation.raise_for_status()
    payload = reconciliation.json()

    assert payload["intervals"] == [
        {
            "start_snapshot": {
                "id": opening_snapshot.json()["id"],
                "snapshot_at": "2026-01-01",
                "balance_minor": 500000,
                "note": "Opening balance",
            },
            "end_snapshot": {
                "id": closing_snapshot.json()["id"],
                "snapshot_at": "2026-02-01",
                "balance_minor": 420000,
                "note": "Month-end balance",
            },
            "is_open": False,
            "tracked_change_minor": -65000,
            "bank_change_minor": -80000,
            "delta_minor": 15000,
            "entry_count": 3,
        },
        {
            "start_snapshot": {
                "id": closing_snapshot.json()["id"],
                "snapshot_at": "2026-02-01",
                "balance_minor": 420000,
                "note": "Month-end balance",
            },
            "end_snapshot": None,
            "is_open": True,
            "tracked_change_minor": -2000,
            "bank_change_minor": None,
            "delta_minor": None,
            "entry_count": 1,
        },
    ]


def test_delete_snapshot_removes_checkpoint_from_account_history(client):
    account = create_account(client)

    snapshot_response = client.post(
        f"/api/v1/accounts/{account['id']}/snapshots",
        json={"snapshot_at": "2026-01-10", "balance_minor": 100000, "note": "Bank balance"},
    )
    snapshot_response.raise_for_status()
    snapshot = snapshot_response.json()

    delete_response = client.delete(f"/api/v1/accounts/{account['id']}/snapshots/{snapshot['id']}")
    assert delete_response.status_code == 204

    snapshots_response = client.get(f"/api/v1/accounts/{account['id']}/snapshots")
    snapshots_response.raise_for_status()
    assert snapshots_response.json() == []

    missing_response = client.delete(f"/api/v1/accounts/{account['id']}/snapshots/{snapshot['id']}")
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Snapshot not found"


def test_dashboard_monthly_aggregations(client):
    account = create_account(client)
    other_currency_account = create_account(client, name="Travel Card")
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        1200,
        "2026-01-02",
        name="Coffee",
        tags=["coffee_snacks"],
        from_entity="Main Checking",
        to_entity="Coffee Shop",
    )
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        500,
        "2026-01-03",
        name="Tuition",
        tags=["education", "one_time"],
        from_entity="Main Checking",
        to_entity="University",
    )
    create_entry(
        client,
        account["id"],
        "INCOME",
        10000,
        "2026-01-03",
        name="Salary",
        tags=["salary"],
        from_entity="Employer",
        to_entity="Main Checking",
    )
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        700,
        "2026-01-04",
        name="Move to card",
        tags=["e_transfer"],
        from_entity="Checking",
        to_entity="Travel Card",
    )
    create_entry(
        client,
        other_currency_account["id"],
        "INCOME",
        700,
        "2026-01-04",
        name="Transfer in",
        tags=["transfer"],
        from_entity="Checking",
        to_entity="Travel Card",
    )
    create_entry(
        client,
        other_currency_account["id"],
        "EXPENSE",
        900,
        "2026-01-04",
        currency_code="USD",
        tags=["travel"],
        name="Flight snack",
    )
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        800,
        "2025-12-28",
        tags=["grocery"],
        name="December groceries",
    )

    dashboard = client.get("/api/v1/dashboard", params={"month": "2026-01"})
    dashboard.raise_for_status()
    payload = dashboard.json()

    assert payload["currency_code"] == "CAD"
    assert payload["kpis"]["expense_total_minor"] == 1700
    assert payload["kpis"]["income_total_minor"] == 10000
    assert payload["kpis"]["average_expense_day_minor"] == 850
    assert payload["kpis"]["median_expense_day_minor"] == 850
    assert payload["kpis"]["spending_days"] == 2

    filter_groups = {item["key"]: item for item in payload["filter_groups"]}
    assert filter_groups["day_to_day"]["total_minor"] == 1200
    assert filter_groups["one_time"]["total_minor"] == 500
    assert filter_groups["fixed"]["total_minor"] == 0
    assert filter_groups["untagged"]["total_minor"] == 0

    jan_second = next(point for point in payload["daily_spending"] if point["date"] == "2026-01-02")
    jan_third = next(point for point in payload["daily_spending"] if point["date"] == "2026-01-03")
    assert jan_second["filter_group_totals"]["day_to_day"] == 1200
    assert jan_third["filter_group_totals"]["one_time"] == 500

    january = next(point for point in payload["monthly_trend"] if point["month"] == "2026-01")
    assert january["expense_total_minor"] == 1700
    assert january["income_total_minor"] == 10000
    assert january["filter_group_totals"]["day_to_day"] == 1200
    assert january["filter_group_totals"]["one_time"] == 500

    assert any(item["label"] == "Main Checking" and item["total_minor"] == 1700 for item in payload["spending_by_from"])
    assert any(item["label"] == "Coffee Shop" and item["total_minor"] == 1200 for item in payload["spending_by_to"])
    assert not any(item["label"] == "Travel Card" for item in payload["spending_by_to"])
    assert any(item["label"] == "coffee_snacks" and item["total_minor"] == 1200 for item in payload["spending_by_tag"])
    assert payload["projection"]["is_current_month"] is False
    assert payload["projection"]["projected_total_minor"] is None
    assert payload["largest_expenses"][0]["name"] == "Coffee"
    assert payload["largest_expenses"][0]["matching_filter_group_keys"] == ["day_to_day"]


def test_dashboard_keeps_generic_entities_even_when_categorized_as_account(client):
    account = create_account(client)
    create_legacy_account_like_entity("Legacy Debit")
    create_legacy_account_like_entity("Legacy Credit")

    create_entry(
        client,
        account["id"],
        "EXPENSE",
        500,
        "2026-01-12",
        name="Legacy transfer",
        tags=["transfer"],
        from_entity="Legacy Debit",
        to_entity="Legacy Credit",
    )

    dashboard = client.get("/api/v1/dashboard", params={"month": "2026-01"})
    dashboard.raise_for_status()
    payload = dashboard.json()

    assert payload["kpis"]["expense_total_minor"] == 500
    assert any(item["label"] == "Legacy Credit" and item["total_minor"] == 500 for item in payload["spending_by_to"])


def test_dashboard_timeline_only_lists_months_with_visible_expenses(client):
    account = create_account(client, name="Checking")
    travel_account = create_account(client, name="Travel Card")

    create_entry(
        client,
        account["id"],
        "EXPENSE",
        1200,
        "2025-11-03",
        name="Groceries",
        from_entity="Checking",
        to_entity="Market",
    )
    create_entry(
        client,
        account["id"],
        "INCOME",
        5000,
        "2025-12-01",
        name="Salary",
        from_entity="Employer",
        to_entity="Checking",
    )
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        900,
        "2026-01-07",
        name="Dinner",
        from_entity="Checking",
        to_entity="Restaurant",
    )
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        700,
        "2026-02-09",
        name="Card transfer out",
        from_entity="Checking",
        to_entity="Travel Card",
    )
    create_entry(
        client,
        travel_account["id"],
        "INCOME",
        700,
        "2026-02-09",
        name="Card transfer in",
        from_entity="Checking",
        to_entity="Travel Card",
    )
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        400,
        "2026-03-11",
        name="Taxi",
        currency_code="USD",
        from_entity="Checking",
        to_entity="Transit",
    )

    response = client.get("/api/v1/dashboard/timeline")
    response.raise_for_status()

    assert response.json() == {"months": ["2025-11", "2026-01"]}


def test_account_routes_are_scoped_by_principal(client):
    account = create_account(client, name="Admin Account")

    scoped_headers = {"X-Bill-Helper-Principal": "alice"}
    list_response = client.get("/api/v1/accounts", headers=scoped_headers)
    list_response.raise_for_status()
    assert list_response.json() == []

    reconciliation_response = client.get(
        f"/api/v1/accounts/{account['id']}/reconciliation",
        headers=scoped_headers,
    )
    assert reconciliation_response.status_code == 404


def test_account_patch_can_clear_markdown_body(client):
    create_response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Notes Account",
            "currency_code": "CAD",
            "is_active": True,
            "markdown_body": "Temporary note",
        },
    )
    create_response.raise_for_status()
    account = create_response.json()

    update_response = client.patch(
        f"/api/v1/accounts/{account['id']}",
        json={"markdown_body": None},
    )
    update_response.raise_for_status()
    assert update_response.json()["markdown_body"] is None


def test_create_account_duplicate_name_returns_conflict(client):
    create_account(client, name="Duplicate Account")

    duplicate_response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Duplicate Account",
            "currency_code": "CAD",
            "is_active": True,
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Entity name already exists"


def test_dashboard_is_scoped_by_principal(client):
    create_account(client, name="Admin Account")
    admin_account = create_account(client, name="Admin Ledger")
    create_entry(
        client,
        admin_account["id"],
        "EXPENSE",
        2000,
        "2026-01-10",
        name="Admin-only expense",
    )

    alice_headers = {"X-Bill-Helper-Principal": "alice"}
    alice_account = create_account(client, name="Alice Account", headers=alice_headers)
    create_entry(
        client,
        alice_account["id"],
        "EXPENSE",
        700,
        "2026-01-11",
        name="Alice expense",
        headers=alice_headers,
    )

    dashboard = client.get("/api/v1/dashboard", params={"month": "2026-01"}, headers=alice_headers)
    dashboard.raise_for_status()
    payload = dashboard.json()

    assert payload["kpis"]["expense_total_minor"] == 700
    assert all(item["name"] != "Admin-only expense" for item in payload["largest_expenses"])


def test_filter_groups_support_default_provisioning_and_custom_overlap(client):
    account = create_account(client)
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        1500,
        "2026-01-15",
        name="Course fee",
        tags=["education", "one_time"],
    )

    list_response = client.get("/api/v1/filter-groups")
    list_response.raise_for_status()
    payload = list_response.json()

    assert [item["key"] for item in payload[:5]] == [
        "day_to_day",
        "one_time",
        "fixed",
        "transfers",
        "untagged",
    ]

    day_to_day_id = next(item["id"] for item in payload if item["key"] == "day_to_day")
    rename_response = client.patch(
        f"/api/v1/filter-groups/{day_to_day_id}",
        json={"name": "daily"},
    )
    assert rename_response.status_code == 409

    create_response = client.post(
        "/api/v1/filter-groups",
        json={
            "name": "education",
            "description": "Track education separately.",
            "rule": {
                "include": {
                    "type": "group",
                    "operator": "AND",
                    "children": [
                        {"type": "condition", "field": "entry_kind", "operator": "is", "value": "EXPENSE"},
                        {"type": "condition", "field": "tags", "operator": "has_any", "value": ["education"]},
                    ],
                }
            },
        },
    )
    create_response.raise_for_status()
    custom_group = create_response.json()
    assert custom_group["key"].startswith("custom_")

    dashboard = client.get("/api/v1/dashboard", params={"month": "2026-01"})
    dashboard.raise_for_status()
    dashboard_payload = dashboard.json()

    filter_groups = {item["name"]: item for item in dashboard_payload["filter_groups"]}
    assert filter_groups["one-time"]["total_minor"] == 1500
    assert filter_groups["education"]["total_minor"] == 1500

    delete_response = client.delete(f"/api/v1/filter-groups/{custom_group['id']}")
    assert delete_response.status_code == 204
