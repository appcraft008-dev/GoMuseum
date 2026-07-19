"""llm_usage 用量记账表(成本可观测性)。"""

import sqlalchemy as sa

from alembic import op

revision = "r1o4"
down_revision = "q1n3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "llm_usage",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("channel", sa.String(32), primary_key=True),
        sa.Column("model", sa.String(64), primary_key=True),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("llm_usage")
