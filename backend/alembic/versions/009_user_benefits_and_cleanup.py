"""Create user_benefits table; drop removed facebook_id column

之前 user_benefits 表只靠应用启动 create_all 创建，未纳入迁移；
facebook_id 随 Facebook 登录一并移除。

Revision ID: 009_user_benefits_and_cleanup
Revises: 008_add_is_guest_field
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "009_user_benefits_and_cleanup"
down_revision = "008_add_is_guest_field"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_benefits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column("user_id", sa.String(255), nullable=True, unique=True, index=True),
        sa.Column("device_id", sa.String(255), nullable=True, index=True),
        sa.Column("recognition_quota", sa.Integer, nullable=False, server_default="10"),
        sa.Column(
            "total_recognitions_used", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("is_premium", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("premium_expires_at", sa.DateTime, nullable=True),
        sa.Column(
            "day_pass_active", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("day_pass_expires_at", sa.DateTime, nullable=True),
        sa.Column(
            "referral_bonus_quota", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at", sa.DateTime, server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False
        ),
        if_not_exists=True,
    )

    op.execute("DROP INDEX IF EXISTS idx_users_facebook_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS facebook_id")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("facebook_id", sa.String(255), nullable=True, unique=True),
    )
    op.create_index("idx_users_facebook_id", "users", ["facebook_id"])
    op.drop_table("user_benefits")
