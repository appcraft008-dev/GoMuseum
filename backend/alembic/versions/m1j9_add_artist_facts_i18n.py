"""add artists.nationality_i18n / notable_works_i18n (作者卡多语,交接③)"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "m1j9_add_artist_facts_i18n"
down_revision = "l1i8_add_recognition_demands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artists",
        sa.Column(
            "nationality_i18n", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "artists",
        sa.Column(
            "notable_works_i18n",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("artists", "notable_works_i18n")
    op.drop_column("artists", "nationality_i18n")
