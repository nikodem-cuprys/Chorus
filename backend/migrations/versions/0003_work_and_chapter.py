"""Works and their chapters

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("language_source", sa.String(10), nullable=True),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("source_name", sa.String(500), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=True),
        sa.Column("source_file", sa.String(200), nullable=True),
        sa.Column("cover_file", sa.String(200), nullable=True),
        sa.Column("is_ao3", sa.Boolean(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("front_matter", sa.JSON(), nullable=False),
        sa.Column("back_matter", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "chapter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "work_id", sa.Integer(), sa.ForeignKey("work.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("notes_before", sa.JSON(), nullable=False),
        sa.Column("blocks", sa.JSON(), nullable=False),
        sa.Column("notes_after", sa.JSON(), nullable=False),
        sa.UniqueConstraint("work_id", "index"),
    )
    op.create_index("ix_chapter_work_id", "chapter", ["work_id"])
    with op.batch_alter_table("job") as batch:
        batch.create_foreign_key(
            "fk_job_work_id_work", "work", ["work_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("job") as batch:
        batch.drop_constraint("fk_job_work_id_work", type_="foreignkey")
    op.drop_index("ix_chapter_work_id", table_name="chapter")
    op.drop_table("chapter")
    op.drop_table("work")
