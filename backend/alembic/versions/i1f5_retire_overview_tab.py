"""retire overview tab: 删 category_sections 里 section_code='overview' 的映射行

默认讲解(default_guide)已取代 overview 作开场;overview 与头条重复,退役为非 tab。
section_types 的 overview 行保留(无害,兼容旧 ObjectContentSection)。幂等。
"""

import sqlalchemy as sa

from alembic import op

revision = "i1f5_retire_overview_tab"
down_revision = "h1e4_add_evidence_pack"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM category_sections WHERE section_code = 'overview'")
    )


def downgrade() -> None:
    pass  # 不恢复(overview 退役为产品决定;需要时重 seed)
