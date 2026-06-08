from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import db


def test_get_db_yields_session():
    gen = db.get_db()
    session = next(gen)
    try:
        assert isinstance(session, Session)
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        gen.close()


def test_engine_is_sqlite_with_check_same_thread():
    # local default DATABASE_URL is sqlite -> connect_args includes check_same_thread
    assert db.engine.url.get_backend_name() == "sqlite"
    assert db.engine.dialect.create_connect_args(db.engine.url)[1].get(
        "check_same_thread"
    ) is False
