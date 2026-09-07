"""记录接地闸算出的存活率(kept/total)。

没有这一列就回答不了"这段为什么挂起":只知道 <0.6,不知道是 0.55(差一点)
还是 0(整段脑补),而两者的处置完全相反。想复查只能重跑一遍闸重新付钱,
而闸本身有随机性(纪律 21),重跑的分数还不是当初那个。

存量为 NULL:当初的分数没留下,补不回来。
"""

import sqlalchemy as sa

from alembic import op

revision = "z1w2"
down_revision = "y1v1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "object_content_sections",
        sa.Column("grounding_ratio", sa.Float(), nullable=True),
    )


def downgrade():
    op.drop_column("object_content_sections", "grounding_ratio")
