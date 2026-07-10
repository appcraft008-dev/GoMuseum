"""add QA audio_key + artists bio_audio (TTS Phase2:问答/作者介绍音频)"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "n1k0_add_audio_keys"
down_revision = "m1j9_add_artist_facts_i18n"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "object_suggested_questions",
        sa.Column("audio_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "artists",
        sa.Column(
            "bio_audio", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),  # {lang: audio_key},按作者共享一份
    )


def downgrade() -> None:
    op.drop_column("artists", "bio_audio")
    op.drop_column("object_suggested_questions", "audio_key")
