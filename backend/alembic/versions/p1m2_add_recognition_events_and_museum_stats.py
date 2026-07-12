"""recognition_events 埋点表(KPI+展陈证据一表两吃)+ museums.stats JSONB。"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "p1m2"
down_revision = "o1l1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recognition_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("museum_slug", sa.String(64), nullable=True, index=True),
        sa.Column("phash", sa.String(64), nullable=False, index=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("top_qid", sa.String(32), nullable=True),
        sa.Column("top_score", sa.Float(), nullable=True),
        sa.Column("confirmed_qid", sa.String(32), nullable=True),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("engine", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
    )
    op.add_column(
        "museums",
        sa.Column(
            "stats",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade():
    op.drop_column("museums", "stats")
    op.drop_table("recognition_events")
