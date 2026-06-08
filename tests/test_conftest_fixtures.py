from sqlalchemy import text


def test_client_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_db_session_works(db_session):
    assert db_session.execute(text("SELECT 1")).scalar() == 1


def test_fake_redis_set_nx(fake_redis):
    assert fake_redis.set("m4:seen:abc", "1", nx=True, ex=10) is True
    assert fake_redis.set("m4:seen:abc", "1", nx=True, ex=10) is None
