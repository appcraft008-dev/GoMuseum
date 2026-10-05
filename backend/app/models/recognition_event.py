"""识别事件埋点:KPI(识别率/引擎分布)+ 展陈证据 + **用户足迹**一表三吃。
每次 recognize() 落一行。

confirmed_qid 由前端确认回填(/recognize/confirm);同 phash 允许多行(不做唯一约束)。

⚠️ 本表**含用户标识**(user_id,见迁移 x1u0)。改动涉及它时记住三处配套:
隐私政策的披露、`delete_user_account` 的断链、`export_user_data` 的导出。
"""

import uuid

from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

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
    # S3:用户否定过的候选(改选时服务端把上一次确认记进来;「都不是」时整组记进来)。
    # 分析口径**按 phash 分组**(同一张照片重拍/重发会多出行):
    #   答案 = 组内 confirmed_qid 集合 − 组内 rejected_qids 并集。
    # confirmed 不清,因为它兼做 24h 计费幂等(confirm_event)与足迹;
    # confirm_event 选中某件时会把它从组内所有行的 rejected 里拿掉,保证上式成立。
    rejected_qids = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    language = Column(String(8), nullable=True)
    # vector|vector_canvas|vector_crops|text|cache|none
    engine = Column(String(16), nullable=False)
    # 是谁拍的。令牌解析得出才填;只有 device_id 的匿名请求留 NULL(那是真匿名,
    # 不能靠 device_id 反查账号 —— 那正是 2026-07 串号计费事故的形态)。
    # 删足迹 = 把这一列清成 NULL:KPI/展陈证据行留下,与账号的关联断掉。
    user_id = Column(String(64), nullable=True)
    # 识别耗时(S1,2026-10-05):总毫秒 + 各阶段毫秒 {"prep":..,"embed":..,"gpt":..}。
    # 只记**跑了的**阶段;从进入 recognize() 起算,不含上传(上传看 nginx rt=)。
    duration_ms = Column(Integer, nullable=True)
    timings = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_recognition_events_user_created", "user_id", "created_at"),
    )
