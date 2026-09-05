"""识别事件记上是谁拍的 —— 让「足迹」有真实数据源。

足迹页(底部四主 tab 之一)读 `/history/*`,而那套端点读的是 `recognition_results`
表。prod 上那张表 **0 行**:唯一会写它的是老端点 `/api/v1/recognition/recognize`,
而 App 从不调它(`recognizeArtwork` 用例全仓库零 UI 调用方)。App 真正走
`/api/v1/recognize` → 写 `recognition_events`(prod 366 行)—— 那张表没有 user_id,
结构上撑不起「按账号回看」。所以足迹不是"数据少",是永远空。

这一列把缺的那半补上。**加法**:nullable,老数据保持 NULL(谁也看不到,
足迹从新识别开始攒);写入侧不填也不报错,埋点纪律不变。

⚠️ 这一列让 recognition_events **从此含有用户标识**,隐私政策里
「这些记录里没有任何用户标识」那句话随之失效 —— 政策与删号/导出的配套改动
必须与本迁移同批上线(见 deployment/website/privacy.html、
AuthService.delete_user_account / export_user_data)。

索引按 (user_id, created_at) 建:足迹查询恒是"某人的、按时间倒序"。
"""

import sqlalchemy as sa

from alembic import op

revision = "x1u0"
down_revision = "w1t9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recognition_events",
        sa.Column("user_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_recognition_events_user_created",
        "recognition_events",
        ["user_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_recognition_events_user_created", "recognition_events")
    op.drop_column("recognition_events", "user_id")
