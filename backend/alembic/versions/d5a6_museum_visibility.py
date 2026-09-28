"""上新馆可见性闸:museums.published_at + users.can_preview。

存量馆**必须**回填成已发布 —— 否则迁移一跑,探索页整页变空。
新馆由 upsert_museum 插入时 published_at 为 NULL,即默认隐身;放出 = 一条 UPDATE。
"""

import sqlalchemy as sa

from alembic import op

revision = "d5a6"
down_revision = "c4z5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("museums", sa.Column("published_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE museums SET published_at = created_at")
    op.add_column(
        "users",
        sa.Column(
            "can_preview", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )


def downgrade():
    op.drop_column("users", "can_preview")
    op.drop_column("museums", "published_at")
