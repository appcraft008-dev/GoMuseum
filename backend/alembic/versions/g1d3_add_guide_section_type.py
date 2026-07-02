"""add 'guide' section_type (默认标准讲解 default_guide 落库需满足 FK)

Revision ID: g1d3_add_guide_section_type
Revises: a3b3_add_content_status
Create Date: 2026-06-29

object_content_sections.section_code 外键 → section_types.code。
默认讲解以 section_code='guide' 落库,故 section_types 须有 'guide' 行。
deploy 跑 `alembic upgrade head` 自动应用,覆盖已存在的 prod/staging DB。幂等。
"""

import sqlalchemy as sa

from alembic import op

revision = "g1d3_add_guide_section_type"
down_revision = "a3b3_add_content_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM section_types WHERE code = 'guide'")
    ).first()
    if not exists:
        bind.execute(
            sa.text(
                "INSERT INTO section_types (code, label_zh, label_en, default_sort) "
                "VALUES ('guide', :zh, :en, 0)"
            ),
            {"zh": "标准导览", "en": "Standard Guide"},
        )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM section_types WHERE code = 'guide'"))
