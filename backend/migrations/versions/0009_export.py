"""Exports: MP3 and M4B exports in the host's exports folder

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "export",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_id",
            sa.Integer(),
            sa.ForeignKey("work.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("folder", sa.String(300), nullable=False),
        sa.Column("files", sa.JSON(), nullable=False),
        sa.Column("parts", sa.JSON(), nullable=False),
        sa.Column("seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_export_work_id", "export", ["work_id"])


def downgrade() -> None:
    op.drop_index("ix_export_work_id", "export")
    op.drop_table("export")
