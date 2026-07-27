"""订单与时长权益表 + 首件免费语音字段(收费模式定案 2026-07-27)。"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "s1p5"
down_revision = "r1o4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purchases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=False),
        # 唯一:恢复购买会重复上报同一 token,靠它防重复发放权益
        sa.Column("store_transaction_id", sa.String(255), nullable=False, unique=True),
        sa.Column("original_transaction_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="purchased"),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_payload", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_purchases_status", "purchases", ["status"])

    op.create_table(
        "entitlements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("entitlement_type", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False, server_default="paris"),
        sa.Column("source_purchase_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="purchased_not_activated",
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_reason", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_entitlements_status", "entitlements", ["status"])
    op.create_index("ix_entitlements_expires_at", "entitlements", ["expires_at"])

    # 首件免费语音:按**作品**认领(不是按 section,也不是"一次券")
    op.add_column(
        "user_benefits", sa.Column("free_audio_qid", sa.String(64), nullable=True)
    )
    op.add_column(
        "user_benefits",
        sa.Column("free_audio_claimed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("user_benefits", "free_audio_claimed_at")
    op.drop_column("user_benefits", "free_audio_qid")
    op.drop_index("ix_entitlements_expires_at", "entitlements")
    op.drop_index("ix_entitlements_status", "entitlements")
    op.drop_table("entitlements")
    op.drop_index("ix_purchases_status", "purchases")
    op.drop_table("purchases")
