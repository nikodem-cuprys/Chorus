"""Assembly: each chapter's assembled audio, and the front and back matter's

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chapter") as batch:
        batch.add_column(sa.Column("audio", sa.JSON(), nullable=True))
    with op.batch_alter_table("work") as batch:
        batch.add_column(
            sa.Column("matter_audio", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )


def downgrade() -> None:
    with op.batch_alter_table("work") as batch:
        batch.drop_column("matter_audio")
    with op.batch_alter_table("chapter") as batch:
        batch.drop_column("audio")
