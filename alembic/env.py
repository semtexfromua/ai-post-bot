import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.models import Base  # noqa: F401  triggers model registration

config = context.config
# Only override if the caller hasn't set a URL (e.g. tests set it via set_main_option).
# Resolve DATABASE_URL from the env first and import the full Settings only as a
# fallback — migrations need just the DB URL, not the runtime secrets the prod
# Settings validator requires.
if not config.get_main_option("sqlalchemy.url"):
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        from app.core.config import settings

        db_url = settings.DATABASE_URL
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
