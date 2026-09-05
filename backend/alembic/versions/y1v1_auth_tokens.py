"""一次性账号令牌表:找回密码 / 邮箱验证。

在此之前**账号没有任何找回手段**:用邮箱密码注册的人忘了密码就永久登不进去,
而通票挂在账号上 —— 等于付了钱的人拿不回自己买的东西,只能靠人工改库救。
触发条件不是"将来某天",是**第一个真实付费用户忘记密码**。

**纯加法**:新表,不动任何既有表/列,老 App 完全无感。

⚠️ `token_hash` 存的是 SHA-256,不是令牌本身 —— 见 app/models/auth_token.py。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "y1v1"
down_revision = "x1u0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_index(
        "ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True
    )
    op.create_index(
        "ix_auth_tokens_user_purpose", "auth_tokens", ["user_id", "purpose"]
    )


def downgrade():
    op.drop_index("ix_auth_tokens_user_purpose", "auth_tokens")
    op.drop_index("ix_auth_tokens_token_hash", "auth_tokens")
    op.drop_index("ix_auth_tokens_user_id", "auth_tokens")
    op.drop_table("auth_tokens")
