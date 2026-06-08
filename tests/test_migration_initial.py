import pathlib

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config
from app.models import Base


def _alembic_config(db_url: str) -> Config:
    root = pathlib.Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migration_creates_all_tables(tmp_path):
    db_file = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_file}"
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    insp = inspect(engine)
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    engine.dispose()


def test_migration_creates_post_fk_to_news_items(tmp_path):
    db_file = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_file}"
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    insp = inspect(engine)
    fks = insp.get_foreign_keys("posts")
    assert len(fks) == 1
    assert fks[0]["referred_table"] == "news_items"
    assert fks[0]["referred_columns"] == ["id"]
    engine.dispose()


def test_migration_unique_constraints_present(tmp_path):
    db_file = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_file}"
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    insp = inspect(engine)
    kw_uniques = {
        tuple(uc["column_names"]) for uc in insp.get_unique_constraints("keywords")
    }
    news_uniques = {
        tuple(uc["column_names"]) for uc in insp.get_unique_constraints("news_items")
    }
    assert ("word",) in kw_uniques
    assert ("content_hash",) in news_uniques
    engine.dispose()


def test_migration_indexes_present(tmp_path):
    db_file = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_file}"
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    insp = inspect(engine)

    def indexed_cols(table):
        return {col for idx in insp.get_indexes(table) for col in idx["column_names"]}

    assert "news_id" in indexed_cols("posts")
    assert "status" in indexed_cols("posts")
    assert "stage" in indexed_cols("error_logs")
    assert "created_at" in indexed_cols("error_logs")
    assert "enabled" in indexed_cols("sources")

    src_uniques = {
        tuple(uc["column_names"]) for uc in insp.get_unique_constraints("sources")
    }
    assert ("url",) in src_uniques
    engine.dispose()
