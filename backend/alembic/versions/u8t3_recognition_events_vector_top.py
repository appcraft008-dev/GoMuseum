"""识别事件记向量前 3 名分数(P2-13)。

0.80–0.85 段第 1 名准确率约 80%,不能整体降直判门槛;要评估「领先第 2 名够多才直判」,
得有真实流量的第 2、3 名分数。存量 NULL,补不回来。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "u8t3"
down_revision = "s6t1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events",
        sa.Column("vector_top", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("recognition_events", "vector_top")
