"""识别事件记「用户否定过的候选」(spec 2026-10-05 S3)。

**加法**:一列 nullable JSONB,老行 NULL。只存作品 qid,不含用户标识,
隐私政策/删号/导出无需配套。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "s3r1"
down_revision = "f1t1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events",
        sa.Column("rejected_qids", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("recognition_events", "rejected_qids")
