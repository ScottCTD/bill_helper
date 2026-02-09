from __future__ import annotations


def create_account(client, name: str = "Checking") -> dict:
    response = client.post(
        "/api/v1/accounts",
        json={
            "name": name,
            "institution": "Test Bank",
            "account_type": "checking",
            "currency_code": "CAD",
            "is_active": True,
        },
    )
    response.raise_for_status()
    return response.json()


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
    )
    response.raise_for_status()
    return response.json()


def test_reconciliation_math(client):
    account = create_account(client)

    snapshot_response = client.post(
        f"/api/v1/accounts/{account['id']}/snapshots",
        json={"snapshot_at": "2026-01-10", "balance_minor": 100000, "note": "Bank balance"},
    )
    snapshot_response.raise_for_status()

    create_entry(client, account["id"], "INCOME", 5000, "2026-01-05")
    create_entry(client, account["id"], "EXPENSE", 2000, "2026-01-08")

    reconciliation = client.get(
        f"/api/v1/accounts/{account['id']}/reconciliation", params={"as_of": "2026-01-10"}
    )
    reconciliation.raise_for_status()
    payload = reconciliation.json()

    assert payload["ledger_balance_minor"] == 3000
    assert payload["snapshot_balance_minor"] == 100000
    assert payload["delta_minor"] == -97000


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
        tags=["daily", "food"],
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
        tags=["non-daily", "education"],
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
        other_currency_account["id"],
        "EXPENSE",
        900,
        "2026-01-04",
        currency_code="USD",
        tags=["daily", "travel"],
        name="Flight snack",
    )
    create_entry(
        client,
        account["id"],
        "EXPENSE",
        800,
        "2025-12-28",
        tags=["daily", "food"],
        name="December groceries",
    )

    dashboard = client.get("/api/v1/dashboard", params={"month": "2026-01"})
    dashboard.raise_for_status()
    payload = dashboard.json()

    assert payload["currency_code"] == "CAD"
    assert payload["kpis"]["expense_total_minor"] == 1700
    assert payload["kpis"]["income_total_minor"] == 10000
    assert payload["kpis"]["daily_expense_total_minor"] == 1200
    assert payload["kpis"]["non_daily_expense_total_minor"] == 500
    assert payload["kpis"]["average_daily_expense_minor"] == 1200
    assert payload["kpis"]["median_daily_expense_minor"] == 1200

    jan_second = next(point for point in payload["daily_spending"] if point["date"] == "2026-01-02")
    jan_third = next(point for point in payload["daily_spending"] if point["date"] == "2026-01-03")
    assert jan_second["daily_expense_minor"] == 1200
    assert jan_third["non_daily_expense_minor"] == 500

    january = next(point for point in payload["monthly_trend"] if point["month"] == "2026-01")
    assert january["expense_total_minor"] == 1700
    assert january["income_total_minor"] == 10000

    assert any(item["label"] == "Main Checking" and item["total_minor"] == 1700 for item in payload["spending_by_from"])
    assert any(item["label"] == "Coffee Shop" and item["total_minor"] == 1200 for item in payload["spending_by_to"])
    assert any(item["label"] == "daily" and item["total_minor"] == 1200 for item in payload["spending_by_tag"])
    assert payload["projection"]["is_current_month"] is False
    assert payload["projection"]["projected_total_minor"] is None
    assert payload["largest_expenses"][0]["name"] == "Coffee"
    assert payload["largest_expenses"][0]["is_daily"] is True
