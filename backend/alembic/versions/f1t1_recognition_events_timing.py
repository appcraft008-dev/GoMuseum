"""识别事件记耗时 —— 找出「转圈 30 秒到 1 分钟」耗在哪一步(spec 2026-10-05 S1)。

**加法**:两列 nullable,老行保持 NULL;写入侧不传也不报错。
存 DB 不只打日志:每次 CD 都会重建容器,docker 日志撑不过一周的观测期。
不含用户标识,隐私政策/删号/导出无需配套。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f1t1"
down_revision = "e6b7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events", sa.Column("duration_ms", sa.Integer(), nullable=True)
    )
    op.add_column(
        "recognition_events",
        sa.Column("timings", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("recognition_events", "timings")
    op.drop_column("recognition_events", "duration_ms")
