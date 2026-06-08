import enum
from datetime import UTC

from sqlalchemy import DateTime, MetaData, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class TZDateTime(TypeDecorator):
    """Store datetimes as UTC; always return tz-aware UTC on read."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"TZDateTime requires a tz-aware datetime, got naive: {value!r}")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is not None:
            return value.replace(tzinfo=UTC)
        return value


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class SourceType(str, enum.Enum):
    site = "site"
    tg = "tg"


class PostStatus(str, enum.Enum):
    new = "new"
    generated = "generated"
    published = "published"
    failed = "failed"


class ErrorStage(str, enum.Enum):
    parse = "parse"
    generate = "generate"
    publish = "publish"
