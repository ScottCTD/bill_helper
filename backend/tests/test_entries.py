from __future__ import annotations

import re


def create_account(client, name: str = "Checking", *, headers: dict[str, str] | None = None) -> str:
    response = client.post(
        "/api/v1/accounts",
        json={
            "name": name,
            "currency_code": "USD",
            "is_active": True,
        },
        headers=headers,
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


def create_entry(
    client,
    account_id: str,
    name: str,
    occurred_at: str = "2026-01-01",
    *,
    headers: dict[str, str] | None = None,
) -> dict:
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
        headers=headers,
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
        json={"target_entry_id": entry2["id"], "link_type": "BUNDLE"},
    )
    link1.raise_for_status()

    link2 = client.post(
        f"/api/v1/entries/{entry2['id']}/links",
        json={"target_entry_id": entry3["id"], "link_type": "BUNDLE"},
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


def test_group_recompute_rebuilds_all_active_components(client):
    from backend.database import get_session_maker
    from backend.models_finance import Entry

    account_id = create_account(client)
    entry1 = create_entry(client, account_id, "Entry 1")
    entry2 = create_entry(client, account_id, "Entry 2")
    entry3 = create_entry(client, account_id, "Entry 3")
    entry4 = create_entry(client, account_id, "Entry 4")

    first_component_link = client.post(
        f"/api/v1/entries/{entry1['id']}/links",
        json={"target_entry_id": entry2["id"], "link_type": "BUNDLE"},
    )
    first_component_link.raise_for_status()
    second_component_link_response = client.post(
        f"/api/v1/entries/{entry3['id']}/links",
        json={"target_entry_id": entry4["id"], "link_type": "BUNDLE"},
    )
    second_component_link_response.raise_for_status()

    first_group_id = client.get(f"/api/v1/entries/{entry1['id']}").json()["group_id"]

    make_session = get_session_maker()
    db = make_session()
    try:
        tampered_entry = db.get(Entry, entry3["id"])
        assert tampered_entry is not None
        tampered_entry.group_id = first_group_id
        db.add(tampered_entry)
        db.commit()
    finally:
        db.close()

    delete_response = client.delete(f"/api/v1/links/{first_component_link.json()['id']}")
    assert delete_response.status_code == 204

    entry1_after = client.get(f"/api/v1/entries/{entry1['id']}").json()
    entry3_after = client.get(f"/api/v1/entries/{entry3['id']}").json()
    entry4_after = client.get(f"/api/v1/entries/{entry4['id']}").json()
    assert entry3_after["group_id"] == entry4_after["group_id"]
    assert entry3_after["group_id"] != entry1_after["group_id"]


def test_entry_routes_are_scoped_by_principal(client):
    account_id = create_account(client)
    admin_entry = create_entry(client, account_id, "Admin only")

    scoped_headers = {"X-Bill-Helper-Principal": "alice"}
    detail_response = client.get(f"/api/v1/entries/{admin_entry['id']}", headers=scoped_headers)
    assert detail_response.status_code == 404

    list_response = client.get("/api/v1/entries", headers=scoped_headers)
    list_response.raise_for_status()
    payload = list_response.json()
    assert payload["total"] == 0
    assert payload["items"] == []


def test_group_routes_are_scoped_by_principal(client):
    admin_account_id = create_account(client)
    admin_first = create_entry(client, admin_account_id, "Admin Entry 1")
    admin_second = create_entry(client, admin_account_id, "Admin Entry 2", occurred_at="2026-01-02")
    admin_link = client.post(
        f"/api/v1/entries/{admin_first['id']}/links",
        json={"target_entry_id": admin_second["id"], "link_type": "BUNDLE"},
    )
    admin_link.raise_for_status()

    alice_headers = {"X-Bill-Helper-Principal": "alice"}
    alice_account_id = create_account(client, name="Alice Checking", headers=alice_headers)
    alice_first = create_entry(client, alice_account_id, "Alice Entry 1", headers=alice_headers)
    alice_second = create_entry(
        client,
        alice_account_id,
        "Alice Entry 2",
        occurred_at="2026-01-03",
        headers=alice_headers,
    )
    alice_link = client.post(
        f"/api/v1/entries/{alice_first['id']}/links",
        json={"target_entry_id": alice_second["id"], "link_type": "BUNDLE"},
        headers=alice_headers,
    )
    alice_link.raise_for_status()

    admin_group_id = client.get(f"/api/v1/entries/{admin_first['id']}").json()["group_id"]

    scoped_groups = client.get("/api/v1/groups", headers=alice_headers)
    scoped_groups.raise_for_status()
    payload = scoped_groups.json()
    assert payload
    assert all(group["latest_entry_name"].startswith("Alice") for group in payload)

    scoped_detail = client.get(f"/api/v1/groups/{admin_group_id}", headers=alice_headers)
    assert scoped_detail.status_code == 404


def test_link_create_rejects_related_link_type(client):
    account_id = create_account(client)
    source = create_entry(client, account_id, "Source")
    target = create_entry(client, account_id, "Target")

    response = client.post(
        f"/api/v1/entries/{source['id']}/links",
        json={"target_entry_id": target["id"], "link_type": "RELATED"},
    )

    assert response.status_code == 422


def test_list_groups_returns_derived_group_summaries(client):
    account_id = create_account(client)
    first = create_entry(client, account_id, "Gym", occurred_at="2026-01-02")
    second = create_entry(client, account_id, "Coffee", occurred_at="2026-01-06")
    third = create_entry(client, account_id, "Groceries", occurred_at="2026-01-05")

    link_response = client.post(
        f"/api/v1/entries/{first['id']}/links",
        json={"target_entry_id": second["id"], "link_type": "BUNDLE"},
    )
    link_response.raise_for_status()

    response = client.get("/api/v1/groups")
    response.raise_for_status()
    payload = response.json()

    assert len(payload) == 1

    merged_group = next(group for group in payload if group["entry_count"] == 2)

    first_after = client.get(f"/api/v1/entries/{first['id']}")
    first_after.raise_for_status()
    second_after = client.get(f"/api/v1/entries/{second['id']}")
    second_after.raise_for_status()
    merged_group_id = first_after.json()["group_id"]
    assert second_after.json()["group_id"] == merged_group_id

    assert merged_group["group_id"] == merged_group_id
    assert merged_group["edge_count"] == 1
    assert merged_group["first_occurred_at"] == "2026-01-02"
    assert merged_group["last_occurred_at"] == "2026-01-06"
    assert merged_group["latest_entry_name"] == "Coffee"

    assert merged_group["group_id"] != third["group_id"]


def test_list_groups_omits_single_entry_components(client):
    account_id = create_account(client)
    create_entry(client, account_id, "Singleton")

    response = client.get("/api/v1/groups")
    response.raise_for_status()
    payload = response.json()

    assert payload == []


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

    assert entry["owner"] == "admin"
    assert entry["owner_user_id"] is not None

    users_response = client.get("/api/v1/users")
    users_response.raise_for_status()
    users = users_response.json()

    current_users = [user for user in users if user["is_current_user"]]
    assert len(current_users) == 1
    assert current_users[0]["name"] == "admin"


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
    assert payload["owner"] == "admin"

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
    assert matching["category"] is None
    assert matching["is_account"] is True
    assert account["id"] == matching["id"]
    assert "entity_id" not in account
    assert account["owner_user_id"] is not None


def test_delete_entity_preserves_denormalized_entry_labels(client):
    account_id = create_account(client)
    from_entity = create_entity(client, "Landlord", category="merchant")
    to_entity = create_entity(client, "Apartment")

    create_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-12",
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

    delete_response = client.delete(f"/api/v1/entities/{from_entity['id']}")
    assert delete_response.status_code == 204

    detail_response = client.get(f"/api/v1/entries/{entry['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert detail["from_entity"] == "Landlord"
    assert detail["from_entity_id"] is None
    assert detail["from_entity_missing"] is True
    assert detail["to_entity"] == "Apartment"
    assert detail["to_entity_id"] == to_entity["id"]
    assert detail["to_entity_missing"] is False

    entities = client.get("/api/v1/entities").json()
    assert all(entity["id"] != from_entity["id"] for entity in entities)


def test_delete_entity_rejects_account_backed_roots(client):
    account_id = create_account(client)

    response = client.delete(f"/api/v1/entities/{account_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Account-backed entities must be managed from Accounts"


def test_delete_account_preserves_entries_and_deletes_snapshots(client):
    account_id = create_account(client)
    destination = create_entity(client, "Broker")

    create_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "TRANSFER",
            "occurred_at": "2026-01-13",
            "name": "Move funds",
            "amount_minor": 50000,
            "currency_code": "USD",
            "from_entity_id": account_id,
            "to_entity_id": destination["id"],
            "tags": ["transfer"],
        },
    )
    create_response.raise_for_status()
    entry = create_response.json()

    snapshot_response = client.post(
        f"/api/v1/accounts/{account_id}/snapshots",
        json={
            "snapshot_at": "2026-01-13",
            "balance_minor": 50000,
            "note": "baseline",
        },
    )
    snapshot_response.raise_for_status()

    delete_response = client.delete(f"/api/v1/accounts/{account_id}")
    assert delete_response.status_code == 204

    detail_response = client.get(f"/api/v1/entries/{entry['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert detail["account_id"] is None
    assert detail["from_entity"] == "Checking"
    assert detail["from_entity_id"] is None
    assert detail["from_entity_missing"] is True
    assert detail["to_entity"] == "Broker"
    assert detail["to_entity_id"] == destination["id"]
    assert detail["to_entity_missing"] is False

    accounts = client.get("/api/v1/accounts")
    accounts.raise_for_status()
    assert accounts.json() == []

    snapshots = client.get(f"/api/v1/accounts/{account_id}/snapshots")
    assert snapshots.status_code == 404

    entities = client.get("/api/v1/entities")
    entities.raise_for_status()
    assert all(entity["id"] != account_id for entity in entities.json())


def test_delete_tag_detaches_existing_entry_links(client):
    account_id = create_account(client)
    entry = create_entry(client, account_id, "Coffee")

    tags_response = client.get("/api/v1/tags")
    tags_response.raise_for_status()
    tag = next(tag for tag in tags_response.json() if tag["name"] == "food")
    assert tag["entry_count"] == 1

    delete_response = client.delete(f"/api/v1/tags/{tag['id']}")
    assert delete_response.status_code == 204

    detail_response = client.get(f"/api/v1/entries/{entry['id']}")
    detail_response.raise_for_status()
    assert detail_response.json()["tags"] == []

    refreshed_tags = client.get("/api/v1/tags")
    refreshed_tags.raise_for_status()
    assert all(existing["id"] != tag["id"] for existing in refreshed_tags.json())


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
        json={"name": "bonus", "color": "#4a90e2", "description": "year-end bonus payouts"},
    )
    new_tag_response.raise_for_status()
    new_tag = new_tag_response.json()
    assert new_tag["name"] == "bonus"
    assert new_tag["color"] == "#4a90e2"
    assert new_tag["description"] == "year-end bonus payouts"
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
        json={"name": "annual-bonus", "color": "#3f72af", "description": "annual bonus income"},
    )
    update_tag_response.raise_for_status()
    updated_tag = update_tag_response.json()
    assert updated_tag["name"] == "annual-bonus"
    assert updated_tag["color"] == "#3f72af"
    assert updated_tag["description"] == "annual bonus income"

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
