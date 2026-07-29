"""记录音频由哪个引擎生成(自托管迁移的前提)。

没有这一列就回答不了"哪些音频还是 tts-1 生成的",
批量替换与覆盖率报表都无从下手 —— 只能靠猜或全量重生成。
"""

import sqlalchemy as sa

from alembic import op

revision = "v1s8"
down_revision = "u1r7"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("object_content_sections", "object_suggested_questions"):
        op.add_column(table, sa.Column("audio_engine", sa.String(32), nullable=True))
    # 迁移进度查询按 (engine, language) 走,建索引避免全表扫
    op.create_index("ix_ocs_audio_engine", "object_content_sections", ["audio_engine"])


def downgrade():
    op.drop_index("ix_ocs_audio_engine", "object_content_sections")
    for table in ("object_content_sections", "object_suggested_questions"):
        op.drop_column(table, "audio_engine")
