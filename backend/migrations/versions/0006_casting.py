"""Casting: the Narrator's Voice of a Work, and each Character's Voice

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work") as batch:
        batch.add_column(
            sa.Column(
                "narrator_voice_id",
                sa.Integer(),
                sa.ForeignKey("voice.id", ondelete="SET NULL", name="fk_work_narrator_voice"),
                nullable=True,
            )
        )
    with op.batch_alter_table("character") as batch:
        batch.add_column(
            sa.Column(
                "voice_id",
                sa.Integer(),
                sa.ForeignKey("voice.id", ondelete="SET NULL", name="fk_character_voice"),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column("voice_auto", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("character") as batch:
        batch.drop_column("voice_auto")
        batch.drop_column("voice_id")
    with op.batch_alter_table("work") as batch:
        batch.drop_column("narrator_voice_id")
