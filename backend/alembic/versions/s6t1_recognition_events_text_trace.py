"""识别事件记文字链复盘(AI 读出的名字与匹配结果)。

**加法**:一列 nullable JSONB,老行 NULL。只存作品名/作者/说明牌文字与匹配分数,
不含用户标识,隐私政策/删号/导出无需配套。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "s6t1"
down_revision = "s5p1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events",
        sa.Column("text_trace", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("recognition_events", "text_trace")
