"""add artists.name_i18n"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "k1h7_add_name_i18n"
down_revision = "j1g6_add_artists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artists",
        sa.Column("name_i18n", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artists", "name_i18n")
