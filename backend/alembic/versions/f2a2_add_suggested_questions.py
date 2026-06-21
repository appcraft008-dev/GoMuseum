"""add object_suggested_questions table

Revision ID: f2a2_add_suggested_questions
Revises: e1a1_add_object_sources
Create Date: 2026-06-21
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "f2a2_add_suggested_questions"
down_revision = "e1a1_add_object_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "object_suggested_questions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            UUID(as_uuid=True),
            sa.ForeignKey("museum_objects.id"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="published"),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "object_id", "language", "sort", name="uq_sq_obj_lang_sort"
        ),
    )
    op.create_index(
        "ix_object_suggested_questions_object_id",
        "object_suggested_questions",
        ["object_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_object_suggested_questions_object_id",
        table_name="object_suggested_questions",
    )
    op.drop_table("object_suggested_questions")
