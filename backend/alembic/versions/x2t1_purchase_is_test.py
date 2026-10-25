"""订单是否测试单:purchases.is_test(加法,可空)。

许可测试单(Play purchaseType=0)/Apple Sandbox 没扣钱,但此前在库里和真实单
一模一样,收入统计会把它们算进去。NULL = 未知(本列上线前的老单,需另行补标)。
"""

import sqlalchemy as sa

from alembic import op

revision = "x2t1"
down_revision = "w1c2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchases", sa.Column("is_test", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("purchases", "is_test")
