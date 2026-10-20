"""Voicing: each line's seed and current take

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("line") as batch:
        batch.add_column(sa.Column("seed", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("take", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("line") as batch:
        batch.drop_column("take")
        batch.drop_column("seed")
