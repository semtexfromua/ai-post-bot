import uuid
from datetime import UTC, datetime

from app.models.base import ErrorStage, PostStatus, SourceType
from app.schemas.error_log import ErrorLogRead
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.schemas.keyword import KeywordCreate, KeywordRead
from app.schemas.post import PostRead
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate


def test_source_create_defaults_enabled_true():
    sc = SourceCreate(type=SourceType.site, name="N", url="https://x")
    assert sc.enabled is True


def test_source_update_all_optional():
    su = SourceUpdate()
    assert su.model_dump(exclude_unset=True) == {}


def test_source_read_has_no_server_secret_fields():
    fields = set(SourceRead.model_fields)
    assert fields == {"id", "type", "name", "url", "enabled", "created_at"}
    # last_seen_msg_id / etag / modified are server-internal and not exposed
    assert "etag" not in fields
    assert "last_seen_msg_id" not in fields


def test_keyword_create_default_lang_none():
    kc = KeywordCreate(word="ai")
    assert kc.lang is None


def test_keyword_read_fields():
    assert set(KeywordRead.model_fields) == {"id", "word", "lang"}


def test_post_read_fields():
    assert set(PostRead.model_fields) == {
        "id",
        "news_id",
        "generated_text",
        "status",
        "published_at",
        "tg_message_id",
        "error",
        "created_at",
    }


def test_error_log_read_fields():
    assert set(ErrorLogRead.model_fields) == {
        "id",
        "created_at",
        "stage",
        "source_id",
        "news_id",
        "post_id",
        "message",
    }


def test_generate_request_defaults_none():
    gr = GenerateRequest()
    assert gr.news_id is None
    assert gr.text is None


def test_generate_response_shape():
    pid = uuid.uuid4()
    resp = GenerateResponse(task_id="t-1", post_id=pid)
    assert resp.task_id == "t-1"
    assert resp.post_id == pid


def test_post_read_from_orm_like_object():
    class _P:
        id = uuid.uuid4()
        news_id = uuid.uuid4()
        generated_text = "hi"
        status = PostStatus.generated
        published_at = None
        tg_message_id = None
        error = None
        created_at = datetime.now(UTC)

    read = PostRead.model_validate(_P())
    assert read.status == PostStatus.generated


def test_error_stage_enum_roundtrips():
    class _E:
        id = uuid.uuid4()
        created_at = datetime.now(UTC)
        stage = ErrorStage.publish
        source_id = None
        news_id = None
        post_id = None
        message = "boom"

    read = ErrorLogRead.model_validate(_E())
    assert read.stage == ErrorStage.publish
