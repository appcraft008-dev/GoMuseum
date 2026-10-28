"""识别事件记拍照来源:recognition_events.capture(加法,可空)。

必看打卡(spec 2026-10-27)只认快门现场拍的识别。"camera" / "gallery";
NULL = 老 App 没传或没扣成费被撤销,永不算打卡。
"""

import sqlalchemy as sa

from alembic import op

revision = "c1m1"
down_revision = "x2t1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events", sa.Column("capture", sa.String(8), nullable=True)
    )


def downgrade():
    op.drop_column("recognition_events", "capture")
