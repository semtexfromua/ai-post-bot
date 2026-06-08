import app.models  # noqa: F401
from app.models.base import Base


def test_all_tables_registered():
    tables = set(Base.metadata.tables)
    assert tables == {
        "sources",
        "keywords",
        "news_items",
        "posts",
        "error_logs",
    }


def test_post_fk_targets_news_items():
    post = Base.metadata.tables["posts"]
    fks = list(post.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "news_items"
    assert fks[0].column.name == "id"


def test_fk_constraint_name_follows_convention():
    post = Base.metadata.tables["posts"]
    fk_names = {fk.constraint.name for fk in post.foreign_keys}
    assert "fk_posts_news_id_news_items" in fk_names
