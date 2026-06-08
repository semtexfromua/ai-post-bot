from app.models.base import (
    NAMING_CONVENTION,
    Base,
    ErrorStage,
    PostStatus,
    SourceType,
)


def test_naming_convention_keys():
    assert set(NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}
    assert NAMING_CONVENTION["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert NAMING_CONVENTION["fk"] == (
        "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    )
    assert NAMING_CONVENTION["pk"] == "pk_%(table_name)s"


def test_base_metadata_carries_naming_convention():
    assert Base.metadata.naming_convention == NAMING_CONVENTION


def test_source_type_enum_values():
    assert SourceType.site.value == "site"
    assert SourceType.tg.value == "tg"


def test_post_status_enum_values():
    assert [s.value for s in PostStatus] == [
        "new",
        "generated",
        "published",
        "failed",
    ]


def test_error_stage_enum_values():
    assert [s.value for s in ErrorStage] == ["parse", "generate", "publish"]
