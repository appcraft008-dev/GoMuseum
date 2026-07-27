"""付费漏斗埋点表(P0-c,2026-07-27)。只做 12 个核心事件。"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "t1q6"
down_revision = "s1p5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "app_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("museum_slug", sa.String(64), nullable=True),
        sa.Column("props", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_app_events_user_id", "app_events", ["user_id"])
    op.create_index("ix_app_events_name", "app_events", ["name"])
    op.create_index("ix_app_events_museum_slug", "app_events", ["museum_slug"])
    # 报告按时间窗聚合,(name, created_at) 是主查询形态
    op.create_index("ix_app_events_name_time", "app_events", ["name", "created_at"])


def downgrade():
    op.drop_index("ix_app_events_name_time", "app_events")
    op.drop_index("ix_app_events_museum_slug", "app_events")
    op.drop_index("ix_app_events_name", "app_events")
    op.drop_index("ix_app_events_user_id", "app_events")
    op.drop_table("app_events")
