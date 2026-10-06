"""识别照片反馈表(spec 2026-10-05 S5)。

新表:用户在确认框里**主动勾选**发送的作品照片的元数据;照片本体在独立私有 R2 桶,
≤90 天或处理完即删,删号即删。隐私政策披露后才打开 PHOTO_FEEDBACK_ENABLED。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "s5p1"
down_revision = "s4c1"
branch_labels = None
depends_on = None

_T = "recognition_photo_feedbacks"
_IDX = (
    "created_at",
    "user_id",
    "device_id",
    "phash",
    "trigger",
    "answer_qid",
    "triage",
    "status",
)


def upgrade():
    op.create_table(
        _T,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("phash", sa.String(64), nullable=False),
        sa.Column("museum_slug", sa.String(64), nullable=True),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("app_version", sa.String(64), nullable=True),
        sa.Column("engine_model", sa.String(64), nullable=True),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("answer_qid", sa.String(32), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("label_text", sa.Text(), nullable=True),
        sa.Column("server_result", postgresql.JSONB(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("image_key", sa.String(255), nullable=True),
        sa.Column("triage", sa.String(16), nullable=True),
        sa.Column("cause", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), server_default="new", nullable=False),
    )
    for col in _IDX:
        op.create_index(op.f(f"ix_{_T}_{col}"), _T, [col])


def downgrade():
    for col in _IDX:
        op.drop_index(op.f(f"ix_{_T}_{col}"), table_name=_T)
    op.drop_table(_T)
