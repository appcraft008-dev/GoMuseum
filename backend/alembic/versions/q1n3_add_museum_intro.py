"""museums 加 description_i18n(AI 接地介绍)+ cover_image_key(得体封面)。"""

import sqlalchemy as sa

from alembic import op

revision = "q1n3"
down_revision = "p1m2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("museums", sa.Column("description_i18n", sa.JSON(), nullable=True))
    op.add_column("museums", sa.Column("cover_image_key", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("museums", "cover_image_key")
    op.drop_column("museums", "description_i18n")
