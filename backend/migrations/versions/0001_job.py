"""The job table

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("queue", sa.String(10), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_job_work_id", "job", ["work_id"])


def downgrade() -> None:
    op.drop_index("ix_job_work_id", table_name="job")
    op.drop_table("job")
