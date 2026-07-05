"""add recognition_demands (未收录需求记录)"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "l1i8_add_recognition_demands"
down_revision = "k1h7_add_name_i18n"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recognition_demands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("museum_slug", sa.String(64), nullable=False, index=True),
        sa.Column("phash", sa.String(64), nullable=False, index=True),
        sa.Column("label_text", sa.Text(), nullable=True),
        sa.Column(
            "gpt_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("museum_slug", "phash", name="uq_demand"),
    )


def downgrade() -> None:
    op.drop_table("recognition_demands")
