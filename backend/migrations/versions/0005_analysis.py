"""Analysis: the Character list, Speakers and Emotions on lines, Narrating Characters

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "character",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_id", sa.Integer(), sa.ForeignKey("work.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("age", sa.String(12), nullable=False),
    )
    op.create_index("ix_character_work_id", "character", ["work_id"])

    with op.batch_alter_table("work") as batch:
        batch.add_column(sa.Column("analysis", sa.JSON(), nullable=True))
    with op.batch_alter_table("chapter") as batch:
        batch.add_column(
            sa.Column(
                "narrating_character_id",
                sa.Integer(),
                sa.ForeignKey(
                    "character.id", ondelete="SET NULL", name="fk_chapter_narrating_character"
                ),
                nullable=True,
            )
        )
    with op.batch_alter_table("line") as batch:
        batch.add_column(sa.Column("speaker", sa.String(10), nullable=True))
        batch.add_column(
            sa.Column(
                "character_id",
                sa.Integer(),
                sa.ForeignKey("character.id", ondelete="SET NULL", name="fk_line_character"),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("emotion", sa.String(12), nullable=True))
        batch.add_column(sa.Column("intensity", sa.String(8), nullable=True))
        batch.create_index("ix_line_character_id", ["character_id"])


def downgrade() -> None:
    with op.batch_alter_table("line") as batch:
        batch.drop_index("ix_line_character_id")
        for column in ("intensity", "emotion", "character_id", "speaker"):
            batch.drop_column(column)
    with op.batch_alter_table("chapter") as batch:
        batch.drop_column("narrating_character_id")
    with op.batch_alter_table("work") as batch:
        batch.drop_column("analysis")
    op.drop_table("character")
