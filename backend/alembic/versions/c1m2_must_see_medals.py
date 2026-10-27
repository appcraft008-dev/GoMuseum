"""必看勋章表 must_see_medals(加法)。spec 2026-10-27 必看打卡 §五.3。"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c1m2"
down_revision = "c1m1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "must_see_medals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("museum_slug", sa.String(64), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "museum_slug", "completed_at"),
    )
    op.create_index(
        "ix_must_see_medals_user_museum", "must_see_medals", ["user_id", "museum_slug"]
    )


def downgrade():
    op.drop_index("ix_must_see_medals_user_museum", table_name="must_see_medals")
    op.drop_table("must_see_medals")
