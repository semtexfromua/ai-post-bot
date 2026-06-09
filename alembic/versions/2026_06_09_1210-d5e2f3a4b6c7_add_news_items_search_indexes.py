"""add search indexes to news_items

Revision ID: d5e2f3a4b6c7
Revises: c4f1a2b3d4e5
Create Date: 2026-06-09 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e2f3a4b6c7"
down_revision: Union[str, None] = "c4f1a2b3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("news_items", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_news_items_published_at"), ["published_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_news_items_source_published_at"),
            ["source", "published_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("news_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_news_items_source_published_at"))
        batch_op.drop_index(batch_op.f("ix_news_items_published_at"))
