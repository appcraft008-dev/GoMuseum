"""add museum_object.sources jsonb

Revision ID: e1a1_add_object_sources
Revises: d6ca257376ac
Create Date: 2026-06-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "e1a1_add_object_sources"
down_revision = "d6ca257376ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "museum_objects",
        sa.Column("sources", JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("museum_objects", "sources")
