"""用户反馈表 —— 内容质量的兜底环(2026-09-18)。

见 `app/models/feedback.py` 的 docstring:为什么不复用 app_events / recognition_demands。

索引按实际查法建:`feedback_report.py` 按 (qid, language, kind) 聚合藏品级、
按 (kind, app_version) 聚合 App 级,人工处置按 status 过滤。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a2x3"
down_revision = "z1w2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedbacks",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("museum_slug", sa.String(64), nullable=True),
        sa.Column("qid", sa.String(32), nullable=True),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("app_version", sa.String(64), nullable=True),
        sa.Column("platform", sa.String(16), nullable=True),
        sa.Column("status", sa.String(16), server_default="new", nullable=False),
    )
    for col in (
        "created_at",
        "user_id",
        "device_id",
        "scope",
        "museum_slug",
        "qid",
        "language",
        "kind",
        "status",
    ):
        op.create_index(f"ix_feedbacks_{col}", "feedbacks", [col])


def downgrade():
    op.drop_table("feedbacks")
