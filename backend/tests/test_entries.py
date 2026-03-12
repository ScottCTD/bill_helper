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


def create_entity(
    client,
    name: str,
    category: str | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> dict:
    payload = {"name": name}
    if category is not None:
        payload["category"] = category
    response = client.post("/api/v1/entities", json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def create_entry(
    client,
    account_id: str,
    name: str,
    occurred_at: str = "2026-01-01",
    kind: str = "EXPENSE",
    *,
    direct_group_id: str | None = None,
    direct_group_member_role: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    payload = {
        "account_id": account_id,
        "kind": kind,
        "occurred_at": occurred_at,
        "name": name,
        "amount_minor": 1234,
        "currency_code": "USD",
        "tags": ["food"],
    }
    if direct_group_id is not None:
        payload["direct_group_id"] = direct_group_id
    if direct_group_member_role is not None:
        payload["direct_group_member_role"] = direct_group_member_role

    response = client.post(
        "/api/v1/entries",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def create_group(
    client,
    name: str,
    group_type: str = "BUNDLE",
    *,
    headers: dict[str, str] | None = None,
) -> dict:
    response = client.post(
        "/api/v1/groups",
        json={"name": name, "group_type": group_type},
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
    assert "entry_count" not in payload["items"][0]["tags"][0]
    assert "status" not in payload["items"][0]


def test_entry_filters_by_filter_group(client):
    account_id = create_account(client)
    coffee = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-04",
            "name": "Coffee",
            "amount_minor": 500,
            "currency_code": "USD",
            "tags": ["coffee_snacks"],
        },
    )
    coffee.raise_for_status()
    rent = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-05",
            "name": "Rent",
            "amount_minor": 120000,
            "currency_code": "USD",
            "tags": ["housing"],
        },
    )
    rent.raise_for_status()

    filter_groups_response = client.get("/api/v1/filter-groups")
    filter_groups_response.raise_for_status()
    day_to_day_group = next(
        group for group in filter_groups_response.json() if group["key"] == "day_to_day"
    )
    fixed_group = next(
        group for group in filter_groups_response.json() if group["key"] == "fixed"
    )

    day_to_day_entries = client.get(
        "/api/v1/entries",
        params={"filter_group_id": day_to_day_group["id"]},
    )
    day_to_day_entries.raise_for_status()
    assert [item["name"] for item in day_to_day_entries.json()["items"]] == ["Coffee"]

    fixed_entries = client.get(
        "/api/v1/entries",
        params={"filter_group_id": fixed_group["id"]},
    )
    fixed_entries.raise_for_status()
    assert [item["name"] for item in fixed_entries.json()["items"]] == ["Rent"]


def test_group_membership_updates_entry_context_and_allows_group_delete_after_unassign(client):
    account_id = create_account(client)
    entry = create_entry(client, account_id, "Entry 1")
    group = create_group(client, "Bills", "BUNDLE")

    membership_response = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": entry["id"]}},
    )
    membership_response.raise_for_status()

    entry_detail = client.get(f"/api/v1/entries/{entry['id']}")
    entry_detail.raise_for_status()
    payload = entry_detail.json()
    assert payload["direct_group"]["id"] == group["id"]
    assert payload["group_path"] == [payload["direct_group"]]

    rename_response = client.patch(f"/api/v1/groups/{group['id']}", json={"name": "Utilities"})
    rename_response.raise_for_status()
    assert rename_response.json()["name"] == "Utilities"

    renamed_entry_detail = client.get(f"/api/v1/entries/{entry['id']}")
    renamed_entry_detail.raise_for_status()
    assert renamed_entry_detail.json()["direct_group"]["name"] == "Utilities"

    blocked_delete = client.delete(f"/api/v1/groups/{group['id']}")
    assert blocked_delete.status_code == 400

    membership_id = membership_response.json()["nodes"][0]["membership_id"]
    remove_response = client.delete(f"/api/v1/groups/{group['id']}/members/{membership_id}")
    assert remove_response.status_code == 204

    entry_detail_after = client.get(f"/api/v1/entries/{entry['id']}")
    entry_detail_after.raise_for_status()
    assert entry_detail_after.json()["direct_group"] is None
    assert entry_detail_after.json()["group_path"] == []

    delete_response = client.delete(f"/api/v1/groups/{group['id']}")
    assert delete_response.status_code == 204


def test_entry_create_update_and_clear_direct_group_membership(client):
    account_id = create_account(client)
    bundle_group = create_group(client, "Bills", "BUNDLE")
    split_group = create_group(client, "Dinner Split", "SPLIT")

    entry = create_entry(client, account_id, "Hydro Bill", direct_group_id=bundle_group["id"])
    assert entry["direct_group"]["id"] == bundle_group["id"]
    assert entry["direct_group_member_role"] is None

    detail_response = client.get(f"/api/v1/entries/{entry['id']}")
    detail_response.raise_for_status()
    assert detail_response.json()["group_path"] == [detail_response.json()["direct_group"]]

    move_response = client.patch(
        f"/api/v1/entries/{entry['id']}",
        json={
            "direct_group_id": split_group["id"],
            "direct_group_member_role": "PARENT",
        },
    )
    move_response.raise_for_status()
    moved = move_response.json()
    assert moved["direct_group"]["id"] == split_group["id"]
    assert moved["direct_group_member_role"] == "PARENT"

    old_group_graph = client.get(f"/api/v1/groups/{bundle_group['id']}")
    old_group_graph.raise_for_status()
    assert old_group_graph.json()["nodes"] == []

    clear_response = client.patch(
        f"/api/v1/entries/{entry['id']}",
        json={"direct_group_id": None},
    )
    clear_response.raise_for_status()
    cleared = clear_response.json()
    assert cleared["direct_group"] is None
    assert cleared["direct_group_member_role"] is None
    assert cleared["group_path"] == []


def test_update_entry_resolves_entity_labels_from_ids(client):
    account_id = create_account(client)
    debit_entity = create_entity(client, "Main Debit Counterparty", category="merchant")
    saving_entity = create_entity(client, "Main Saving Counterparty", category="merchant")

    create_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "TRANSFER",
            "occurred_at": "2026-02-14",
            "name": "Transfer to savings",
            "amount_minor": 180000,
            "currency_code": "USD",
            "from_entity_id": debit_entity["id"],
            "from_entity": None,
            "to_entity_id": saving_entity["id"],
            "to_entity": None,
            "tags": [],
        },
    )
    create_response.raise_for_status()
    entry = create_response.json()

    assert entry["from_entity"] == "Main Debit Counterparty"
    assert entry["to_entity"] == "Main Saving Counterparty"

    update_response = client.patch(
        f"/api/v1/entries/{entry['id']}",
        json={
            "from_entity_id": debit_entity["id"],
            "from_entity": None,
            "to_entity_id": saving_entity["id"],
            "to_entity": None,
        },
    )
    update_response.raise_for_status()
    updated = update_response.json()

    assert updated["from_entity_id"] == debit_entity["id"]
    assert updated["to_entity_id"] == saving_entity["id"]
    assert updated["from_entity"] == "Main Debit Counterparty"
    assert updated["to_entity"] == "Main Saving Counterparty"

    detail_response = client.get(f"/api/v1/entries/{entry['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert detail["from_entity"] == "Main Debit Counterparty"
    assert detail["to_entity"] == "Main Saving Counterparty"


def test_entry_group_assignment_validates_split_role_requirements(client):
    account_id = create_account(client)
    split_group = create_group(client, "Split Dinner", "SPLIT")

    create_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-02",
            "name": "Dinner",
            "amount_minor": 1234,
            "currency_code": "USD",
            "tags": ["food"],
            "direct_group_id": split_group["id"],
        },
    )
    assert create_response.status_code == 400

    entry = create_entry(client, account_id, "Dinner Parent")
    update_response = client.patch(
        f"/api/v1/entries/{entry['id']}",
        json={
            "direct_group_id": split_group["id"],
        },
    )
    assert update_response.status_code == 400


def test_bundle_group_graph_and_summary_include_empty_groups(client):
    account_id = create_account(client)
    first = create_entry(client, account_id, "Gym", occurred_at="2026-01-02")
    second = create_entry(client, account_id, "Coffee", occurred_at="2026-01-06")
    create_group(client, "Empty Group", "BUNDLE")
    group = create_group(client, "Bundle Group", "BUNDLE")

    add_first = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": first["id"]}},
    )
    add_first.raise_for_status()
    add_second = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": second["id"]}},
    )
    add_second.raise_for_status()

    groups_response = client.get("/api/v1/groups")
    groups_response.raise_for_status()
    groups = groups_response.json()
    assert {group_item["name"] for group_item in groups} == {"Bundle Group", "Empty Group"}

    bundle_summary = next(group_item for group_item in groups if group_item["name"] == "Bundle Group")
    assert bundle_summary["group_type"] == "BUNDLE"
    assert bundle_summary["direct_member_count"] == 2
    assert bundle_summary["direct_entry_count"] == 2
    assert bundle_summary["direct_child_group_count"] == 0
    assert bundle_summary["descendant_entry_count"] == 2
    assert bundle_summary["first_occurred_at"] == "2026-01-02"
    assert bundle_summary["last_occurred_at"] == "2026-01-06"

    graph_response = client.get(f"/api/v1/groups/{group['id']}")
    graph_response.raise_for_status()
    graph = graph_response.json()
    assert graph["name"] == "Bundle Group"
    assert graph["group_type"] == "BUNDLE"
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
    assert {node["node_type"] for node in graph["nodes"]} == {"ENTRY"}
    assert {node["currency_code"] for node in graph["nodes"]} == {"USD"}


def test_split_group_validation_and_graph(client):
    account_id = create_account(client)
    parent = create_entry(client, account_id, "Dinner", occurred_at="2026-01-02")
    child_income = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "INCOME",
            "occurred_at": "2026-01-03",
            "name": "Alice paid back",
            "amount_minor": 617,
            "currency_code": "USD",
            "tags": ["food"],
        },
    )
    child_income.raise_for_status()
    other_child_income = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "INCOME",
            "occurred_at": "2026-01-04",
            "name": "Bob paid back",
            "amount_minor": 617,
            "currency_code": "USD",
            "tags": ["food"],
        },
    )
    other_child_income.raise_for_status()
    invalid_child = create_entry(client, account_id, "Invalid expense child", occurred_at="2026-01-05")
    group = create_group(client, "Split Dinner", "SPLIT")

    parent_response = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": parent["id"]}, "member_role": "PARENT"},
    )
    parent_response.raise_for_status()
    child_response = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": child_income.json()["id"]}, "member_role": "CHILD"},
    )
    child_response.raise_for_status()
    second_child_response = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": other_child_income.json()["id"]}, "member_role": "CHILD"},
    )
    second_child_response.raise_for_status()

    invalid_response = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": invalid_child["id"]}, "member_role": "CHILD"},
    )
    assert invalid_response.status_code == 400

    graph_response = client.get(f"/api/v1/groups/{group['id']}")
    graph_response.raise_for_status()
    graph = graph_response.json()
    parent_node = next(node for node in graph["nodes"] if node["member_role"] == "PARENT")
    assert parent_node["name"] == "Dinner"
    assert len(graph["edges"]) == 2
    assert all(edge["group_type"] == "SPLIT" for edge in graph["edges"])


def test_recurring_group_validation_and_graph(client):
    account_id = create_account(client)
    first = create_entry(client, account_id, "Rent Jan", occurred_at="2026-01-01")
    second = create_entry(client, account_id, "Rent Feb", occurred_at="2026-02-01")
    third = create_entry(client, account_id, "Rent Mar", occurred_at="2026-03-01")
    invalid_income = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "INCOME",
            "occurred_at": "2026-04-01",
            "name": "Refund",
            "amount_minor": 1234,
            "currency_code": "USD",
            "tags": ["housing"],
        },
    )
    invalid_income.raise_for_status()
    group = create_group(client, "Monthly Rent", "RECURRING")

    for entry in (first, second, third):
        response = client.post(
            f"/api/v1/groups/{group['id']}/members",
            json={"target": {"target_type": "entry", "entry_id": entry["id"]}},
        )
        response.raise_for_status()

    invalid_response = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": invalid_income.json()["id"]}},
    )
    assert invalid_response.status_code == 400

    graph_response = client.get(f"/api/v1/groups/{group['id']}")
    graph_response.raise_for_status()
    graph = graph_response.json()
    assert [node["name"] for node in graph["nodes"]] == ["Rent Jan", "Rent Feb", "Rent Mar"]
    assert len(graph["edges"]) == 2
    assert graph["edges"][0]["group_type"] == "RECURRING"


def test_nested_groups_depth_one_and_no_sharing(client):
    account_id = create_account(client)
    child_entry = create_entry(client, account_id, "Netflix", occurred_at="2026-01-01")
    other_entry = create_entry(client, account_id, "Spotify", occurred_at="2026-01-02")
    second_parent = create_group(client, "Entertainment", "BUNDLE")
    parent = create_group(client, "Monthly Bills", "BUNDLE")
    child = create_group(client, "Streaming", "BUNDLE")
    second_child = create_group(client, "Podcasts", "BUNDLE")

    add_child_entry = client.post(
        f"/api/v1/groups/{child['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": child_entry["id"]}},
    )
    add_child_entry.raise_for_status()

    attach_child = client.post(
        f"/api/v1/groups/{parent['id']}/members",
        json={"target": {"target_type": "child_group", "group_id": child["id"]}},
    )
    attach_child.raise_for_status()

    nested_response = client.post(
        f"/api/v1/groups/{child['id']}/members",
        json={"target": {"target_type": "child_group", "group_id": second_child["id"]}},
    )
    assert nested_response.status_code == 400

    shared_response = client.post(
        f"/api/v1/groups/{second_parent['id']}/members",
        json={"target": {"target_type": "child_group", "group_id": child["id"]}},
    )
    assert shared_response.status_code == 400

    add_second_child_entry = client.post(
        f"/api/v1/groups/{second_child['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": other_entry["id"]}},
    )
    add_second_child_entry.raise_for_status()
    parented_nested_child = client.post(
        f"/api/v1/groups/{child['id']}/members",
        json={"target": {"target_type": "child_group", "group_id": second_child["id"]}},
    )
    assert parented_nested_child.status_code == 400

    entry_detail = client.get(f"/api/v1/entries/{child_entry['id']}")
    entry_detail.raise_for_status()
    assert [group["name"] for group in entry_detail.json()["group_path"]] == ["Monthly Bills", "Streaming"]

    graph_response = client.get(f"/api/v1/groups/{parent['id']}")
    graph_response.raise_for_status()
    graph = graph_response.json()
    assert graph["direct_child_group_count"] == 1
    assert graph["descendant_entry_count"] == 1
    assert graph["nodes"][0]["node_type"] == "GROUP"


def test_entry_routes_are_scoped_by_principal(client, auth_headers):
    account_id = create_account(client)
    admin_entry = create_entry(client, account_id, "Admin only")

    scoped_headers = auth_headers("alice")
    detail_response = client.get(f"/api/v1/entries/{admin_entry['id']}", headers=scoped_headers)
    assert detail_response.status_code == 404

    list_response = client.get("/api/v1/entries", headers=scoped_headers)
    list_response.raise_for_status()
    payload = list_response.json()
    assert payload["total"] == 0
    assert payload["items"] == []


def test_group_routes_are_scoped_by_principal(client, auth_headers):
    admin_account_id = create_account(client)
    admin_entry = create_entry(client, admin_account_id, "Admin Entry 1")
    admin_group = create_group(client, "Admin Group", "BUNDLE")
    admin_add = client.post(
        f"/api/v1/groups/{admin_group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": admin_entry["id"]}},
    )
    admin_add.raise_for_status()

    alice_headers = auth_headers("alice")
    alice_account_id = create_account(client, name="Alice Checking", headers=alice_headers)
    alice_entry = create_entry(client, alice_account_id, "Alice Entry 1", headers=alice_headers)
    alice_group = create_group(client, "Alice Group", "BUNDLE", headers=alice_headers)
    alice_add = client.post(
        f"/api/v1/groups/{alice_group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": alice_entry["id"]}},
        headers=alice_headers,
    )
    alice_add.raise_for_status()

    scoped_groups = client.get("/api/v1/groups", headers=alice_headers)
    scoped_groups.raise_for_status()
    payload = scoped_groups.json()
    assert [group["name"] for group in payload] == ["Alice Group"]

    scoped_detail = client.get(f"/api/v1/groups/{admin_group['id']}", headers=alice_headers)
    assert scoped_detail.status_code == 404


def test_soft_delete_entry_removes_group_membership(client):
    account_id = create_account(client)
    entry = create_entry(client, account_id, "Child")
    group = create_group(client, "Temp Group", "BUNDLE")
    add_response = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"target": {"target_type": "entry", "entry_id": entry["id"]}},
    )
    add_response.raise_for_status()

    delete_response = client.delete(f"/api/v1/entries/{entry['id']}")
    assert delete_response.status_code == 204

    group_response = client.get(f"/api/v1/groups/{group['id']}")
    group_response.raise_for_status()
    payload = group_response.json()
    assert payload["nodes"] == []
    assert payload["descendant_entry_count"] == 0


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


def test_catalog_patch_endpoints_reject_empty_payloads(client):
    account_id = create_account(client)
    entity = create_entity(client, "Merchant")
    group = create_group(client, "Bills", "BUNDLE")

    tag_response = client.post(
        "/api/v1/tags",
        json={"name": "utilities"},
    )
    tag_response.raise_for_status()
    tag = tag_response.json()

    users_response = client.get("/api/v1/users")
    users_response.raise_for_status()
    user_id = users_response.json()[0]["id"]

    assert client.patch(f"/api/v1/accounts/{account_id}", json={}).status_code == 422
    assert client.patch(f"/api/v1/entities/{entity['id']}", json={}).status_code == 422
    assert client.patch(f"/api/v1/tags/{tag['id']}", json={}).status_code == 422
    assert client.patch(f"/api/v1/groups/{group['id']}", json={}).status_code == 422
    assert client.patch(f"/api/v1/admin/users/{user_id}", json={}).status_code == 422


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


def test_create_entity_rejects_account_category(client):
    response = client.post(
        "/api/v1/entities",
        json={"name": "Travel Card", "category": "account"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Account category is reserved for Accounts. Use /accounts instead."


def test_entity_update_rejects_account_category(client):
    entity = create_entity(client, "Travel Card", category="merchant")

    response = client.patch(
        f"/api/v1/entities/{entity['id']}",
        json={"category": "account"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Account category is reserved for Accounts. Use /accounts instead."


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


def test_currencies_are_scoped_by_principal(client, auth_headers):
    admin_account_id = create_account(client, name="Admin Checking")
    admin_entry_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": admin_account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-12",
            "name": "Admin EUR expense",
            "amount_minor": 1000,
            "currency_code": "EUR",
            "tags": ["food"],
        },
    )
    admin_entry_response.raise_for_status()

    alice_headers = auth_headers("alice")
    alice_account_id = create_account(client, name="Alice Checking", headers=alice_headers)
    alice_entry_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": alice_account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-13",
            "name": "Alice special expense",
            "amount_minor": 1500,
            "currency_code": "ZZZ",
            "tags": ["food"],
        },
        headers=alice_headers,
    )
    alice_entry_response.raise_for_status()

    currencies_response = client.get("/api/v1/currencies", headers=alice_headers)
    currencies_response.raise_for_status()
    currencies = {currency["code"]: currency for currency in currencies_response.json()}

    assert "EUR" not in currencies
    assert currencies["ZZZ"]["entry_count"] == 1
    assert currencies["ZZZ"]["is_placeholder"] is True
    assert currencies["USD"]["entry_count"] == 0
    assert currencies["USD"]["is_placeholder"] is False


def test_catalog_reads_are_scoped_by_principal(client, auth_headers):
    admin_vendor = create_entity(client, "Admin Vendor")

    admin_account_id = create_account(client, name="Admin Checking")
    admin_entry_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": admin_account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-14",
            "name": "Admin vendor expense",
            "amount_minor": 1000,
            "currency_code": "USD",
            "from_entity_id": admin_vendor["id"],
            "tags": ["food"],
        },
    )
    admin_entry_response.raise_for_status()

    alice_headers = auth_headers("alice")
    alice_vendor = create_entity(client, "Alice Vendor", headers=alice_headers)
    alice_account_id = create_account(client, name="Alice Checking", headers=alice_headers)
    alice_entry_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": alice_account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-15",
            "name": "Alice vendor expense",
            "amount_minor": 1500,
            "currency_code": "USD",
            "from_entity_id": alice_vendor["id"],
            "tags": ["food"],
        },
        headers=alice_headers,
    )
    alice_entry_response.raise_for_status()

    admin_entities_response = client.get("/api/v1/entities")
    admin_entities_response.raise_for_status()
    admin_entities = admin_entities_response.json()
    admin_vendor_row = next(entity for entity in admin_entities if entity["id"] == admin_vendor["id"])
    alice_vendor_row = next(entity for entity in admin_entities if entity["id"] == alice_vendor["id"])
    assert admin_vendor_row["from_count"] == 1
    assert admin_vendor_row["entry_count"] == 1
    assert alice_vendor_row["from_count"] == 1
    assert alice_vendor_row["entry_count"] == 1
    assert any(entity["name"] == "Admin Checking" for entity in admin_entities)
    assert any(entity["name"] == "Alice Checking" for entity in admin_entities)

    alice_entities_response = client.get("/api/v1/entities", headers=alice_headers)
    alice_entities_response.raise_for_status()
    alice_entities = alice_entities_response.json()
    alice_vendor_row = next(entity for entity in alice_entities if entity["id"] == alice_vendor["id"])
    assert alice_vendor_row["from_count"] == 1
    assert alice_vendor_row["entry_count"] == 1
    assert any(entity["name"] == "Alice Checking" for entity in alice_entities)
    assert all(entity["id"] != admin_vendor["id"] for entity in alice_entities)
    assert all(entity["name"] != "Admin Checking" for entity in alice_entities)

    admin_tags_response = client.get("/api/v1/tags")
    admin_tags_response.raise_for_status()
    admin_food_tags = [tag for tag in admin_tags_response.json() if tag["name"] == "food"]
    assert len(admin_food_tags) == 2
    assert sorted(tag["entry_count"] for tag in admin_food_tags) == [1, 1]

    alice_tags_response = client.get("/api/v1/tags", headers=alice_headers)
    alice_tags_response.raise_for_status()
    alice_food = next(tag for tag in alice_tags_response.json() if tag["name"] == "food")
    assert alice_food["entry_count"] == 1


def test_entities_list_includes_same_currency_net_amounts(client):
    account_id = create_account(client)
    cafe = create_entity(client, "Cafe")

    expense_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-10",
            "name": "Coffee run",
            "amount_minor": 1200,
            "currency_code": "USD",
            "from_entity": "Main Checking",
            "to_entity_id": cafe["id"],
            "tags": [],
        },
    )
    expense_response.raise_for_status()

    income_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "INCOME",
            "occurred_at": "2026-01-11",
            "name": "Refund",
            "amount_minor": 300,
            "currency_code": "USD",
            "from_entity_id": cafe["id"],
            "to_entity": "Main Checking",
            "tags": [],
        },
    )
    income_response.raise_for_status()

    entities_response = client.get("/api/v1/entities")
    entities_response.raise_for_status()
    cafe_row = next(entity for entity in entities_response.json() if entity["id"] == cafe["id"])

    assert cafe_row["entry_count"] == 2
    assert cafe_row["net_amount_minor"] == -900
    assert cafe_row["net_amount_currency_code"] == "USD"
    assert cafe_row["net_amount_mixed_currencies"] is False


def test_entities_list_marks_mixed_currency_net_amounts(client):
    account_id = create_account(client)
    airline = create_entity(client, "Airline")

    usd_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-10",
            "name": "Seat upgrade",
            "amount_minor": 1200,
            "currency_code": "USD",
            "from_entity": "Main Checking",
            "to_entity_id": airline["id"],
            "tags": [],
        },
    )
    usd_response.raise_for_status()

    eur_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-11",
            "name": "Airport snack",
            "amount_minor": 600,
            "currency_code": "EUR",
            "from_entity": "Main Checking",
            "to_entity_id": airline["id"],
            "tags": [],
        },
    )
    eur_response.raise_for_status()

    entities_response = client.get("/api/v1/entities")
    entities_response.raise_for_status()
    airline_row = next(entity for entity in entities_response.json() if entity["id"] == airline["id"])

    assert airline_row["entry_count"] == 2
    assert airline_row["net_amount_minor"] is None
    assert airline_row["net_amount_currency_code"] is None
    assert airline_row["net_amount_mixed_currencies"] is True
