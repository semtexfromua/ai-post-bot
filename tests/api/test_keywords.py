import uuid


def test_create_keyword_201(client):
    resp = client.post("/api/v1/keywords", json={"word": "ai", "lang": "en"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["word"] == "ai"
    assert body["lang"] == "en"
    assert set(body.keys()) == {"id", "word", "lang"}


def test_create_keyword_default_lang_null(client):
    resp = client.post("/api/v1/keywords", json={"word": "робот"})
    assert resp.status_code == 201
    assert resp.json()["lang"] is None


def test_list_keywords_envelope(client):
    client.post("/api/v1/keywords", json={"word": "a"})
    client.post("/api/v1/keywords", json={"word": "b"})
    resp = client.get("/api/v1/keywords")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["data"]) == 2


def test_update_keyword_patch(client):
    created = client.post("/api/v1/keywords", json={"word": "old"}).json()
    resp = client.patch(f"/api/v1/keywords/{created['id']}", json={"word": "new"})
    assert resp.status_code == 200
    assert resp.json()["word"] == "new"


def test_get_keyword_404(client):
    resp = client.get(f"/api/v1/keywords/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_delete_keyword_204(client):
    created = client.post("/api/v1/keywords", json={"word": "del"}).json()
    resp = client.delete(f"/api/v1/keywords/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/keywords/{created['id']}").status_code == 404


def test_create_keyword_duplicate_word_returns_409(client):
    assert client.post("/api/v1/keywords", json={"word": "gpt"}).status_code == 201
    resp = client.post("/api/v1/keywords", json={"word": "gpt"})
    assert resp.status_code == 409
