from __future__ import annotations


def test_taxonomy_category_assignment_for_tags_and_entities(client):
    tag_response = client.post(
        "/api/v1/tags",
        json={"name": "groceries", "type": "food"},
    )
    tag_response.raise_for_status()
    tag = tag_response.json()
    assert tag["type"] == "food"

    entity_response = client.post(
        "/api/v1/entities",
        json={"name": "Costco", "category": "merchant"},
    )
    entity_response.raise_for_status()
    entity = entity_response.json()
    assert entity["category"] == "merchant"

    list_tags = client.get("/api/v1/tags")
    list_tags.raise_for_status()
    payload_tags = list_tags.json()
    assert payload_tags[0]["type"] == "food"

    list_entities = client.get("/api/v1/entities")
    list_entities.raise_for_status()
    payload_entities = list_entities.json()
    assert payload_entities[0]["category"] == "merchant"


def test_taxonomy_endpoints_expose_terms_with_usage_counts(client):
    client.post("/api/v1/tags", json={"name": "groceries", "type": "food"}).raise_for_status()
    client.post("/api/v1/tags", json={"name": "restaurant", "type": "food"}).raise_for_status()
    client.post("/api/v1/entities", json={"name": "Costco", "category": "merchant"}).raise_for_status()

    taxonomies = client.get("/api/v1/taxonomies")
    taxonomies.raise_for_status()
    taxonomy_keys = {row["key"] for row in taxonomies.json()}
    assert "tag_type" in taxonomy_keys
    assert "entity_category" in taxonomy_keys

    tag_terms_response = client.get("/api/v1/taxonomies/tag_type/terms")
    tag_terms_response.raise_for_status()
    tag_terms = tag_terms_response.json()
    food = next(term for term in tag_terms if term["name"] == "food")
    assert food["usage_count"] == 2

    entity_terms_response = client.get("/api/v1/taxonomies/entity_category/terms")
    entity_terms_response.raise_for_status()
    entity_terms = entity_terms_response.json()
    merchant = next(term for term in entity_terms if term["name"] == "merchant")
    assert merchant["usage_count"] == 1


def test_taxonomy_term_create_and_rename(client):
    create_term = client.post(
        "/api/v1/taxonomies/tag_type/terms",
        json={"name": "Utilities"},
    )
    create_term.raise_for_status()
    term = create_term.json()
    assert term["name"] == "utilities"

    rename_term = client.patch(
        f"/api/v1/taxonomies/tag_type/terms/{term['id']}",
        json={"name": "Recurring Bills"},
    )
    rename_term.raise_for_status()
    renamed = rename_term.json()
    assert renamed["name"] == "recurring bills"

    terms = client.get("/api/v1/taxonomies/tag_type/terms")
    terms.raise_for_status()
    payload = terms.json()
    assert any(item["name"] == "recurring bills" for item in payload)


def test_taxonomy_term_create_rejects_duplicates(client):
    first_create = client.post(
        "/api/v1/taxonomies/tag_type/terms",
        json={"name": "Utilities"},
    )
    first_create.raise_for_status()

    duplicate_create = client.post(
        "/api/v1/taxonomies/tag_type/terms",
        json={"name": "  utilities  "},
    )
    assert duplicate_create.status_code == 409
    assert duplicate_create.json()["detail"] == "Term already exists"


def test_taxonomy_term_create_rejects_parent_term_field(client):
    response = client.post(
        "/api/v1/taxonomies/tag_type/terms",
        json={"name": "utilities", "parent_term_id": "abc"},
    )
    assert response.status_code == 422


def test_entity_update_response_reads_taxonomy_category_after_term_rename(client):
    entity_response = client.post(
        "/api/v1/entities",
        json={"name": "Costco", "category": "merchant"},
    )
    entity_response.raise_for_status()
    entity = entity_response.json()
    assert entity["category"] == "merchant"

    terms_response = client.get("/api/v1/taxonomies/entity_category/terms")
    terms_response.raise_for_status()
    merchant_term = next(term for term in terms_response.json() if term["name"] == "merchant")

    rename_response = client.patch(
        f"/api/v1/taxonomies/entity_category/terms/{merchant_term['id']}",
        json={"name": "service provider"},
    )
    rename_response.raise_for_status()
    assert rename_response.json()["name"] == "service provider"

    update_response = client.patch(
        f"/api/v1/entities/{entity['id']}",
        json={"name": "Costco Warehouse"},
    )
    update_response.raise_for_status()
    updated = update_response.json()
    assert updated["name"] == "Costco Warehouse"
    assert updated["category"] == "service provider"


def test_entity_category_terms_support_description(client):
    create_term = client.post(
        "/api/v1/taxonomies/entity_category/terms",
        json={"name": "Service", "description": "Service providers and contractors"},
    )
    create_term.raise_for_status()
    term = create_term.json()
    assert term["name"] == "service"
    assert term["description"] == "Service providers and contractors"

    rename_term = client.patch(
        f"/api/v1/taxonomies/entity_category/terms/{term['id']}",
        json={"description": "Service providers and recurring vendors"},
    )
    rename_term.raise_for_status()
    renamed = rename_term.json()
    assert renamed["description"] == "Service providers and recurring vendors"


def test_taxonomy_mutations_are_scoped_to_current_principal(client, auth_headers):
    scoped_headers = auth_headers("alice")

    entity_response = client.post("/api/v1/entities", json={"name": "Local Shop"}, headers=scoped_headers)
    entity_response.raise_for_status()

    tag_response = client.post("/api/v1/tags", json={"name": "groceries"}, headers=scoped_headers)
    tag_response.raise_for_status()

    term_response = client.post(
        "/api/v1/taxonomies/tag_type/terms",
        json={"name": "food"},
        headers=scoped_headers,
    )
    term_response.raise_for_status()
