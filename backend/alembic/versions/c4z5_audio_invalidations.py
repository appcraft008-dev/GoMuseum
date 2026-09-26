"""音频失效台账表(契约纪律 37 第②层)。

每一条已有音频被清空/删除都留一行:key、所属行、语种、当时的文字、哪条命令。
2026-09-14 那次跨馆作者音频脱钩 12 天没人发现,原文也过了备份保留期 ——
有这张表就能照着挂回去,GC 也据此不删这些文件。纯加法,不动任何已有表。
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c4z5"
down_revision = "b3y4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audio_invalidations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity", sa.String(16), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artist_qid", sa.String(32), nullable=True),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("section_code", sa.String(32), nullable=True),
        sa.Column("qa_sort", sa.Integer(), nullable=True),
        sa.Column("audio_key", sa.Text(), nullable=False),
        sa.Column("audio_engine", sa.String(32), nullable=True),
        sa.Column("old_text", sa.Text(), nullable=True),
        sa.Column("change", sa.String(16), nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("allowed", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
    )
    for col in ("entity", "object_id", "artist_qid", "audio_key"):
        op.create_index(f"ix_audio_invalidations_{col}", "audio_invalidations", [col])


def downgrade():
    op.drop_table("audio_invalidations")
