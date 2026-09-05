"""识别事件埋点:KPI(识别率/引擎分布)+ 展陈证据 + **用户足迹**一表三吃。
每次 recognize() 落一行。

confirmed_qid 由前端确认回填(/recognize/confirm);同 phash 允许多行(不做唯一约束)。

⚠️ 本表**含用户标识**(user_id,见迁移 x1u0)。改动涉及它时记住三处配套:
隐私政策的披露、`delete_user_account` 的断链、`export_user_data` 的导出。
"""

import uuid

from sqlalchemy import Column, DateTime, Float, Index, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class RecognitionEvent(Base):
    __tablename__ = "recognition_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    museum_slug = Column(String(64), nullable=True, index=True)
    phash = Column(String(64), nullable=False, index=True)
    outcome = Column(String(16), nullable=False)  # match|candidates|unrecognized
    top_qid = Column(String(32), nullable=True)
    top_score = Column(Float, nullable=True)
    confirmed_qid = Column(String(32), nullable=True)  # 用户确认回填
    language = Column(String(8), nullable=True)
    engine = Column(String(16), nullable=False)  # vector|vector_crops|text|cache|none
    # 是谁拍的。令牌解析得出才填;只有 device_id 的匿名请求留 NULL(那是真匿名,
    # 不能靠 device_id 反查账号 —— 那正是 2026-07 串号计费事故的形态)。
    # 删足迹 = 把这一列清成 NULL:KPI/展陈证据行留下,与账号的关联断掉。
    user_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_recognition_events_user_created", "user_id", "created_at"),
    )
