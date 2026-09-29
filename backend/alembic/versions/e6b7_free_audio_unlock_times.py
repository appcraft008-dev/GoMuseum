"""免费语音解锁清单改存解锁时刻(D8:音频权利统一为 7 天)。

user_benefits.free_audio_qids:["Q1", ...] → {"Q1": "<解锁时刻 iso>", ...}
存量没有真实解锁时刻,统一记为**本迁移执行的时刻**(spec 2026-09-28 §3.7 ④:
零真实用户,从上线时刻起算 7 天,不写迁移特例)。

回滚兼容:老代码读这一列是 `list(...)`,对 dict 得到的正是 qid 列表 —— 不用反向迁移。
"""

import json
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

revision = "e6b7"
down_revision = "d5a6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    now = datetime.now(timezone.utc).isoformat()
    rows = bind.execute(
        sa.text(
            "SELECT id, free_audio_qids FROM user_benefits "
            "WHERE free_audio_qids IS NOT NULL"
        )
    ).fetchall()
    for row_id, raw in rows:
        val = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(val, list):
            continue  # 已是新形状
        bind.execute(
            sa.text(
                "UPDATE user_benefits SET free_audio_qids = CAST(:v AS JSON) WHERE id = :id"
            ),
            {"v": json.dumps({q: now for q in val if q}), "id": row_id},
        )


def downgrade():
    pass  # 见模块说明:老代码能直接读新形状
