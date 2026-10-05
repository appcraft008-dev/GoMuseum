"""识别事件记「确认从哪来」(spec 2026-10-05 S4)。

**加法**:一列 nullable,老行 NULL(=候选确认,计过费)。只存来源标签,不含用户标识,
隐私政策/删号/导出无需配套。用途:搜索路径的确认只记答案、不占「一次拍照只扣一次」的锁。
"""

import sqlalchemy as sa

from alembic import op

revision = "s4c1"
down_revision = "s3r1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events",
        sa.Column("confirm_source", sa.String(16), nullable=True),
    )


def downgrade():
    op.drop_column("recognition_events", "confirm_source")
