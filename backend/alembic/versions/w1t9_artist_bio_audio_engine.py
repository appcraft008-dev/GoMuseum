"""作者介绍音频也要记录引擎(补齐 v1s8 漏掉的第三处)。

音频 key 存在**三处**:object_content_sections、object_suggested_questions、
**artists.bio_audio**。v1s8 只给前两处加了 audio_engine —— 于是作者介绍音频
既回答不了"是哪个引擎生成的",也进不了迁移队列,自托管替换完会残留旧音色。
而 bio 是**按作者共享**的,一条音频在该作者所有作品下播放,影响面乘以作品数。

形状与 bio_audio 一致({lang: engine}),两者永远同进同退。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "w1t9"
down_revision = "v1s8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "artists",
        sa.Column(
            "bio_audio_engine",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("artists", "bio_audio_engine")
