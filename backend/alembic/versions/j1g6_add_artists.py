"""add artists table (作者一等实体)"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "j1g6_add_artists"
down_revision = "i1f5_retire_overview_tab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artists",
        sa.Column("qid", sa.String(length=32), primary_key=True),
        sa.Column("name_zh", sa.String(length=255), nullable=True),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("birth", sa.String(length=16), nullable=True),
        sa.Column("death", sa.String(length=16), nullable=True),
        sa.Column("nationality", sa.String(length=128), nullable=True),
        sa.Column(
            "notable_works", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("bio", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("artists")
