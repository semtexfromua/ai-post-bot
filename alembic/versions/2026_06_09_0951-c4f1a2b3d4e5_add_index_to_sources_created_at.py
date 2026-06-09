"""add index to sources.created_at

Revision ID: c4f1a2b3d4e5
Revises: 9fb12f376407
Create Date: 2026-06-09 09:51:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f1a2b3d4e5"
down_revision: Union[str, None] = "9fb12f376407"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sources", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_sources_created_at"), ["created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("sources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sources_created_at"))
