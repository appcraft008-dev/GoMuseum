"""add evidence_pack JSONB column to museum_objects"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "h1e4_add_evidence_pack"
down_revision = "g1d3_add_guide_section_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "museum_objects",
        sa.Column(
            "evidence_pack", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("museum_objects", "evidence_pack")
