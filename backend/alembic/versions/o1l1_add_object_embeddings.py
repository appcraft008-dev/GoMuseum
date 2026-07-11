"""object_embeddings 表 + recognition_demands.museum_slug 可空(全局识别)。"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "o1l1"
down_revision = "n1k0_add_audio_keys"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "object_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            UUID(as_uuid=True),
            sa.ForeignKey("museum_objects.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "image_id",
            UUID(as_uuid=True),
            sa.ForeignKey("object_images.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("vec", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("image_id", "model", name="uq_embedding_image_model"),
    )
    op.alter_column(
        "recognition_demands", "museum_slug", existing_type=sa.String(64), nullable=True
    )


def downgrade():
    op.alter_column(
        "recognition_demands",
        "museum_slug",
        existing_type=sa.String(64),
        nullable=False,
    )
    op.drop_table("object_embeddings")
