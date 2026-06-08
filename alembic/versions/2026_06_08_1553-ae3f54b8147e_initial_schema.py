"""initial schema

Revision ID: ae3f54b8147e
Revises:
Create Date: 2026-06-08 15:53:14.878213

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ae3f54b8147e"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "stage",
            sa.Enum("parse", "generate", "publish", name="errorstage"),
            nullable=False,
        ),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("news_id", sa.Uuid(), nullable=True),
        sa.Column("post_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("traceback", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_error_logs")),
    )
    op.create_table(
        "keywords",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("word", sa.String(), nullable=False),
        sa.Column("lang", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keywords")),
        sa.UniqueConstraint("word", name=op.f("uq_keywords_word")),
    )
    op.create_table(
        "news_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("raw_text", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_items")),
        sa.UniqueConstraint("content_hash", name=op.f("uq_news_items_content_hash")),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("site", "tg", name="sourcetype"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_seen_msg_id", sa.Integer(), nullable=True),
        sa.Column("etag", sa.String(), nullable=True),
        sa.Column("modified", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
    )
    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("news_id", sa.Uuid(), nullable=False),
        sa.Column("generated_text", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("new", "generated", "published", "failed", name="poststatus"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("tg_message_id", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["news_id"],
            ["news_items.id"],
            name=op.f("fk_posts_news_id_news_items"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_posts")),
    )


def downgrade() -> None:
    op.drop_table("posts")
    op.drop_table("sources")
    op.drop_table("news_items")
    op.drop_table("keywords")
    op.drop_table("error_logs")
