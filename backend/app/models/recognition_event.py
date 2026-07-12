"""识别事件埋点:KPI(识别率/引擎分布)+ 展陈证据一表两吃。每次 recognize() 落一行。

confirmed_qid 由前端确认回填(/recognize/confirm);同 phash 允许多行(不做唯一约束)。"""

import uuid

from sqlalchemy import Column, DateTime, Float, String, func
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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
