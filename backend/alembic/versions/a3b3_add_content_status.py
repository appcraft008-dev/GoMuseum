"""add museum_objects.content_status

Revision ID: a3b3_add_content_status
Revises: f2a2_add_suggested_questions
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "a3b3_add_content_status"
down_revision = "f2a2_add_suggested_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "museum_objects",
        sa.Column(
            "content_status",
            sa.String(length=16),
            nullable=False,
            server_default="stub",
        ),
    )


def downgrade() -> None:
    op.drop_column("museum_objects", "content_status")
