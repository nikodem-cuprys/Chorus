"""The Script's lines

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "line",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_id", sa.Integer(), sa.ForeignKey("work.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapter.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("part", sa.String(10), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("paragraph", sa.Integer(), nullable=True),
        sa.Column("last_paragraph", sa.Integer(), nullable=True),
        sa.Column("spans", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("passage", sa.String(16), nullable=False),
        sa.Column("voiced", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("work_id", "position"),
    )
    op.create_index("ix_line_work_id", "line", ["work_id"])
    op.create_index("ix_line_chapter_id", "line", ["chapter_id"])


def downgrade() -> None:
    op.drop_table("line")
