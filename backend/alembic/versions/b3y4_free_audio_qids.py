"""免费语音跟着识别走:user_benefits.free_audio_qids(2026-09-19)。

旧规则「免费试听一件」和「免费识别 5 次」是两个互不对齐的数字,用户识别第二件
点播放被弹墙,观感是"那 5 次识别是假的"。新规则只留一个数字:
**识别出来的作品,主讲解段都能听**,上限天然等于免费识别次数。

纯加法:新列 nullable,老的 free_audio_qid/lang/claimed_at 三列保留不动
(删列不可回滚)。不做回填 —— 尚无真实用户,存量只有测试账号。
"""

import sqlalchemy as sa

from alembic import op

revision = "b3y4"
down_revision = "a2x3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_benefits", sa.Column("free_audio_qids", sa.JSON(), nullable=True)
    )


def downgrade():
    op.drop_column("user_benefits", "free_audio_qids")
