def test_create_source_201(client):
    resp = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "Example", "url": "https://example.com"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Example"
    assert body["type"] == "site"
    assert body["enabled"] is True
    assert "id" in body and "created_at" in body
    # Read schema must NOT leak server-internal fields
    assert "etag" not in body
    assert "last_seen_msg_id" not in body


def test_list_sources_envelope(client):
    client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "A", "url": "https://a"},
    )
    client.post(
        "/api/v1/sources",
        json={"type": "tg", "name": "B", "url": "@b"},
    )
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["data"]) == 2


def test_get_source_by_id(client):
    created = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "G", "url": "https://g"},
    ).json()
    resp = client.get(f"/api/v1/sources/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_source_404(client):
    import uuid

    resp = client.get(f"/api/v1/sources/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_update_source_patch(client):
    created = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "Old", "url": "https://old"},
    ).json()
    resp = client.patch(
        f"/api/v1/sources/{created['id']}",
        json={"name": "New", "enabled": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New"
    assert body["enabled"] is False
    assert body["url"] == "https://old"


def test_delete_source_204(client):
    created = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "D", "url": "https://d"},
    ).json()
    resp = client.delete(f"/api/v1/sources/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/sources/{created['id']}").status_code == 404


def test_create_source_rejects_file_scheme(client):
    resp = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "x", "url": "file:///etc/passwd"},
    )
    assert resp.status_code == 422


def test_create_source_allows_tg_username(client):
    resp = client.post(
        "/api/v1/sources",
        json={"type": "tg", "name": "c", "url": "@chan"},
    )
    assert resp.status_code == 201


def test_create_source_allows_https(client):
    resp = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "h", "url": "https://example.com/feed"},
    )
    assert resp.status_code == 201


def test_update_source_rejects_file_scheme(client):
    created = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "U", "url": "https://u"},
    ).json()
    resp = client.patch(
        f"/api/v1/sources/{created['id']}",
        json={"url": "file:///x"},
    )
    assert resp.status_code == 422
    # patch without url still works
    resp2 = client.patch(
        f"/api/v1/sources/{created['id']}",
        json={"name": "Updated"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Updated"
