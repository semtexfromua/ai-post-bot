import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import db


def test_get_db_yields_session(monkeypatch):
    # Hermetic: pin SessionLocal to in-memory SQLite so the test exercises the
    # get_db() contract (yields a working session, closes it) without depending
    # on an external DATABASE_URL being reachable.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(db, "SessionLocal", sessionmaker(engine, class_=Session))
    gen = db.get_db()
    session = next(gen)
    try:
        assert isinstance(session, Session)
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        gen.close()


def test_engine_is_sqlite_with_check_same_thread():
    # sqlite-specific connect_arg; skip when DATABASE_URL points elsewhere (e.g. CI Postgres)
    if db.engine.url.get_backend_name() != "sqlite":
        pytest.skip("DATABASE_URL is not sqlite in this environment")
    assert db.engine.url.get_backend_name() == "sqlite"
    assert (
        db.engine.dialect.create_connect_args(db.engine.url)[1].get("check_same_thread")
        is False
    )
