"""馆封面署名:museums.cover_credit(加法,可空)。

封面多取自 Wikimedia Commons 建筑照(CC-BY/BY-SA),公开展示要写作者;
此前只存了图,没存署名。藏品图回落时署名仍在 object_images.credit。
"""

import sqlalchemy as sa
from alembic import op

revision = "w1c2"
down_revision = "v9u4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("museums", sa.Column("cover_credit", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("museums", "cover_credit")
