from app.models.base import ErrorStage
from app.models.error_log import ErrorLog


def test_list_errors_envelope(client, db_session):
    db_session.add(
        ErrorLog(stage=ErrorStage.generate, message="gen boom")
    )
    db_session.add(
        ErrorLog(stage=ErrorStage.publish, message="pub boom")
    )
    db_session.commit()

    resp = client.get("/api/v1/errors")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "count"}
    assert body["count"] == 2
    messages = {e["message"] for e in body["data"]}
    assert messages == {"gen boom", "pub boom"}
    # Read schema excludes traceback
    assert "traceback" not in body["data"][0]


def test_list_errors_stage_filter(client, db_session):
    db_session.add(ErrorLog(stage=ErrorStage.parse, message="parse err"))
    db_session.add(ErrorLog(stage=ErrorStage.publish, message="publish err"))
    db_session.commit()

    resp = client.get("/api/v1/errors", params={"stage": "publish"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["data"][0]["stage"] == "publish"


def test_list_errors_empty(client):
    resp = client.get("/api/v1/errors")
    assert resp.status_code == 200
    assert resp.json() == {"data": [], "count": 0}
