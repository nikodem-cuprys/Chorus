"""Job control: each job's arguments, its current Celery message, and a pause or cancel request

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("job") as batch:
        batch.add_column(
            sa.Column("kwargs", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch.add_column(sa.Column("task_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("request", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("job") as batch:
        batch.drop_column("request")
        batch.drop_column("task_id")
        batch.drop_column("kwargs")
