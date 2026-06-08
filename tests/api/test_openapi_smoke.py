def test_openapi_registers_v1_paths(client):
    spec = client.get("/openapi.json").json()
    paths = set(spec["paths"].keys())
    assert "/api/v1/sources" in paths
    assert "/api/v1/sources/{source_id}" in paths
    assert "/api/v1/keywords" in paths
    assert "/api/v1/posts" in paths
    assert "/api/v1/generate" in paths
    assert "/api/v1/errors" in paths


def test_generate_path_is_202(client):
    spec = client.get("/openapi.json").json()
    post_op = spec["paths"]["/api/v1/generate"]["post"]
    assert "202" in post_op["responses"]
