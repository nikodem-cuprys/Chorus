"""The voice table

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("age", sa.String(12), nullable=False),
        sa.Column("accent", sa.String(40), nullable=False),
        sa.Column("timbre", sa.JSON(), nullable=False),
        sa.Column("narrator_ok", sa.Boolean(), nullable=False),
        sa.Column("built_in", sa.Boolean(), nullable=False),
        sa.Column("clips", sa.JSON(), nullable=False),
        sa.Column("credit", sa.String(200), nullable=True),
    )
    op.create_index("ix_voice_language", "voice", ["language"])


def downgrade() -> None:
    op.drop_index("ix_voice_language", table_name="voice")
    op.drop_table("voice")
