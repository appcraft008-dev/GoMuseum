"""免费试听收敛到 (作品, 语言, 主讲解段)。

此前只记 free_audio_qid,而一件作品有多个段落(guide/背景/分析/问答/作者介绍),
每段独立 TTS,再乘 10 种语言 —— "免费一件"实际是几十次生成。
"""

import sqlalchemy as sa

from alembic import op

revision = "u1r7"
down_revision = "t1q6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_benefits", sa.Column("free_audio_lang", sa.String(16), nullable=True)
    )


def downgrade():
    op.drop_column("user_benefits", "free_audio_lang")
