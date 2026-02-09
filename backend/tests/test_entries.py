from __future__ import annotations

import re


def create_account(client) -> str:
    response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Checking",
            "institution": "Test Bank",
            "account_type": "checking",
            "currency_code": "USD",
            "is_active": True,
        },
    )
    response.raise_for_status()
    return response.json()["id"]


def create_entity(client, name: str, category: str | None = None) -> dict:
    payload = {"name": name}
    if category is not None:
        payload["category"] = category
    response = client.post("/api/v1/entities", json=payload)
    response.raise_for_status()
    return response.json()


def create_entry(client, account_id: str, name: str, occurred_at: str = "2026-01-01") -> dict:
    response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": occurred_at,
            "name": name,
            "amount_minor": 1234,
            "currency_code": "USD",
            "tags": ["food"],
        },
    )
    response.raise_for_status()
    return response.json()


def test_entry_filters_and_tags(client):
    account_id = create_account(client)
    create_entry(client, account_id, "Coffee", occurred_at="2026-01-04")
    create_entry(client, account_id, "Lunch", occurred_at="2026-01-05")

    response = client.get("/api/v1/entries", params={"tag": "food", "start_date": "2026-01-05"})
    response.raise_for_status()
    payload = response.json()

    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Lunch"
    assert payload["items"][0]["tags"][0]["name"] == "food"
    assert "status" not in payload["items"][0]


def test_link_create_and_delete_recomputes_groups(client):
    account_id = create_account(client)
    entry1 = create_entry(client, account_id, "Entry 1")
    entry2 = create_entry(client, account_id, "Entry 2")
    entry3 = create_entry(client, account_id, "Entry 3")

    link1 = client.post(
        f"/api/v1/entries/{entry1['id']}/links",
        json={"target_entry_id": entry2["id"], "link_type": "RELATED"},
    )
    link1.raise_for_status()

    link2 = client.post(
        f"/api/v1/entries/{entry2['id']}/links",
        json={"target_entry_id": entry3["id"], "link_type": "RELATED"},
    )
    link2.raise_for_status()

    after_link = client.get(f"/api/v1/entries/{entry3['id']}").json()
    shared_group = after_link["group_id"]
    assert client.get(f"/api/v1/entries/{entry1['id']}").json()["group_id"] == shared_group
    assert client.get(f"/api/v1/entries/{entry2['id']}").json()["group_id"] == shared_group

    delete_response = client.delete(f"/api/v1/links/{link1.json()['id']}")
    assert delete_response.status_code == 204

    entry1_after = client.get(f"/api/v1/entries/{entry1['id']}").json()
    entry2_after = client.get(f"/api/v1/entries/{entry2['id']}").json()
    entry3_after = client.get(f"/api/v1/entries/{entry3['id']}").json()

    assert entry2_after["group_id"] == entry3_after["group_id"]
    assert entry1_after["group_id"] != entry2_after["group_id"]


def test_soft_delete_entry_removes_links(client):
    account_id = create_account(client)
    entry1 = create_entry(client, account_id, "Parent")
    entry2 = create_entry(client, account_id, "Child")

    link_response = client.post(
        f"/api/v1/entries/{entry1['id']}/links",
        json={"target_entry_id": entry2["id"], "link_type": "SPLIT"},
    )
    link_response.raise_for_status()

    delete_response = client.delete(f"/api/v1/entries/{entry2['id']}")
    assert delete_response.status_code == 204

    detail = client.get(f"/api/v1/entries/{entry1['id']}")
    detail.raise_for_status()
    assert detail.json()["links"] == []


def test_entry_defaults_owner_to_current_user(client):
    account_id = create_account(client)
    entry = create_entry(client, account_id, "Default owner")

    assert entry["owner"] == "scott"
    assert entry["owner_user_id"] is not None

    users_response = client.get("/api/v1/users")
    users_response.raise_for_status()
    users = users_response.json()

    current_users = [user for user in users if user["is_current_user"]]
    assert len(current_users) == 1
    assert current_users[0]["name"] == "scott"


def test_entry_accepts_entity_ids_and_owner_user_id(client):
    account_id = create_account(client)
    from_entity = create_entity(client, "Main Checking")
    to_entity = create_entity(client, "Coffee Shop")
    users_response = client.get("/api/v1/users")
    users_response.raise_for_status()
    owner_user = users_response.json()[0]

    response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-09",
            "name": "Coffee",
            "amount_minor": 600,
            "currency_code": "USD",
            "from_entity_id": from_entity["id"],
            "to_entity_id": to_entity["id"],
            "owner_user_id": owner_user["id"],
            "tags": ["food"],
        },
    )
    response.raise_for_status()
    payload = response.json()

    assert payload["from_entity_id"] == from_entity["id"]
    assert payload["to_entity_id"] == to_entity["id"]
    assert payload["owner_user_id"] == owner_user["id"]
    assert payload["from_entity"] == "Main Checking"
    assert payload["to_entity"] == "Coffee Shop"
    assert payload["owner"] == "scott"

    tags_response = client.get("/api/v1/tags")
    tags_response.raise_for_status()
    tags = tags_response.json()
    assert any(tag["name"] == "food" for tag in tags)


def test_entity_update_syncs_denormalized_entry_labels(client):
    account_id = create_account(client)
    from_entity = create_entity(client, "Landlord", category="merchant")
    to_entity = create_entity(client, "Apartment")

    create_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-10",
            "name": "Rent",
            "amount_minor": 200000,
            "currency_code": "USD",
            "from_entity_id": from_entity["id"],
            "to_entity_id": to_entity["id"],
            "tags": ["housing"],
        },
    )
    create_response.raise_for_status()
    entry = create_response.json()

    rename_response = client.patch(
        f"/api/v1/entities/{from_entity['id']}",
        json={"name": "Property Manager", "category": "service-provider"},
    )
    rename_response.raise_for_status()
    renamed = rename_response.json()
    assert renamed["category"] == "service-provider"

    refreshed = client.get(f"/api/v1/entries/{entry['id']}")
    refreshed.raise_for_status()
    payload = refreshed.json()
    assert payload["from_entity"] == "Property Manager"
    assert payload["from_entity_id"] == from_entity["id"]


def test_accounts_are_entities_linked_to_users(client):
    account_id = create_account(client)
    account = client.get("/api/v1/accounts").json()[0]

    entities_response = client.get("/api/v1/entities")
    entities_response.raise_for_status()
    entities = entities_response.json()
    entity_names = {entity["name"] for entity in entities}
    assert "Checking" in entity_names
    matching = next(entity for entity in entities if entity["name"] == "Checking")
    assert matching["category"] == "account"
    assert account["entity_id"] == matching["id"]
    assert account["owner_user_id"] is not None


def test_tag_management_and_currency_catalog(client):
    account_id = create_account(client)
    create_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "INCOME",
            "occurred_at": "2026-01-11",
            "name": "Freelance",
            "amount_minor": 55000,
            "currency_code": "EUR",
            "tags": ["work"],
        },
    )
    create_response.raise_for_status()
    custom_currency_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-11",
            "name": "Special expense",
            "amount_minor": 1000,
            "currency_code": "ZZZ",
            "tags": ["work"],
        },
    )
    custom_currency_response.raise_for_status()

    new_tag_response = client.post(
        "/api/v1/tags",
        json={"name": "bonus", "color": "#4a90e2"},
    )
    new_tag_response.raise_for_status()
    new_tag = new_tag_response.json()
    assert new_tag["name"] == "bonus"
    assert new_tag["color"] == "#4a90e2"
    assert new_tag["entry_count"] == 0

    auto_color_tag_response = client.post(
        "/api/v1/tags",
        json={"name": "side-project"},
    )
    auto_color_tag_response.raise_for_status()
    auto_color_tag = auto_color_tag_response.json()
    assert auto_color_tag["name"] == "side-project"
    assert isinstance(auto_color_tag["color"], str)
    assert re.match(r"^#[0-9a-f]{6}$", auto_color_tag["color"])

    list_tags_response = client.get("/api/v1/tags")
    list_tags_response.raise_for_status()
    tags = list_tags_response.json()
    work_tag = next(tag for tag in tags if tag["name"] == "work")
    assert work_tag["entry_count"] == 2
    assert isinstance(work_tag["color"], str)
    assert re.match(r"^#[0-9a-f]{6}$", work_tag["color"])

    update_tag_response = client.patch(
        f"/api/v1/tags/{new_tag['id']}",
        json={"name": "annual-bonus", "color": "#3f72af"},
    )
    update_tag_response.raise_for_status()
    updated_tag = update_tag_response.json()
    assert updated_tag["name"] == "annual-bonus"
    assert updated_tag["color"] == "#3f72af"

    currencies_response = client.get("/api/v1/currencies")
    currencies_response.raise_for_status()
    currencies = currencies_response.json()

    cny = next(currency for currency in currencies if currency["code"] == "CNY")
    eur = next(currency for currency in currencies if currency["code"] == "EUR")
    zzz = next(currency for currency in currencies if currency["code"] == "ZZZ")
    usd = next(currency for currency in currencies if currency["code"] == "USD")
    cad = next(currency for currency in currencies if currency["code"] == "CAD")
    assert cny["entry_count"] == 0
    assert cny["is_placeholder"] is False
    assert cad["entry_count"] >= 0
    assert cad["is_placeholder"] is False
    assert eur["entry_count"] == 1
    assert eur["is_placeholder"] is True
    assert zzz["entry_count"] == 1
    assert zzz["is_placeholder"] is True
    assert usd["entry_count"] >= 0
    assert usd["is_placeholder"] is False
