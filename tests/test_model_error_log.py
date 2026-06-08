import uuid
from datetime import UTC, datetime

from app.models.base import ErrorStage
from app.models.error_log import ErrorLog


def test_create_error_log_row(db):
    log = ErrorLog(stage=ErrorStage.generate, message="boom")
    db.add(log)
    db.commit()
    db.refresh(log)
    assert isinstance(log.id, uuid.UUID)
    assert log.stage is ErrorStage.generate
    assert log.message == "boom"
    assert log.source_id is None
    assert log.news_id is None
    assert log.post_id is None
    assert log.traceback is None
    assert log.created_at.tzinfo is not None


def test_error_log_stage_enum_round_trip(db):
    log = ErrorLog(
        stage=ErrorStage.publish,
        message="m",
        post_id=uuid.uuid4(),
        traceback="Traceback...",
    )
    db.add(log)
    db.commit()
    fetched = db.get(ErrorLog, log.id)
    assert fetched.stage is ErrorStage.publish
    assert fetched.traceback == "Traceback..."


def test_error_log_created_at_is_utc(db):
    log = ErrorLog(stage=ErrorStage.parse, message="m")
    db.add(log)
    db.commit()
    db.refresh(log)
    assert log.created_at.utcoffset() == UTC.utcoffset(datetime.now())
