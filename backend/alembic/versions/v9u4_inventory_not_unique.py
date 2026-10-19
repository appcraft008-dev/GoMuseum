"""同馆同馆藏号允许多件:唯一约束 → 普通索引。

奥赛油画/雕塑两套编号都写作 RF n,Wikidata 上同号两件不同作品(RF 166 = Regnault 油画
Q17491121 = Chapu 雕塑 Q76465029)。唯一约束 (museum_id, inventory_number) 只容一件,
另一件导入时被跳过(2026-10-19 统计奥赛 53 组)。作品身份本来就靠 qid(全局唯一),
馆藏号只是查找键,留普通索引保查询速度。

downgrade 在已有同号两件时会失败——那是对的:先决定删哪件再降级。
"""

from alembic import op

revision = "v9u4"
down_revision = "u8t3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("uq_object_museum_inventory", "museum_objects", type_="unique")
    op.create_index(
        "ix_object_museum_inventory",
        "museum_objects",
        ["museum_id", "inventory_number"],
    )


def downgrade():
    op.drop_index("ix_object_museum_inventory", table_name="museum_objects")
    op.create_unique_constraint(
        "uq_object_museum_inventory",
        "museum_objects",
        ["museum_id", "inventory_number"],
    )
