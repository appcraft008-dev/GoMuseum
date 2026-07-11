"""未收录需求记录:识别不中即记,按 (馆, 感知哈希) 幂等聚合计数。
需求自适应(契约R5):目录跟真实拍摄需求生长。spec 2026-07-03-recognition-design。"""

import uuid

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.core.database import Base


class RecognitionDemand(Base):
    __tablename__ = "recognition_demands"
    __table_args__ = (UniqueConstraint("museum_slug", "phash", name="uq_demand"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    museum_slug = Column(String(64), nullable=True, index=True)
    phash = Column(String(64), nullable=False, index=True)
    label_text = Column(Text, nullable=True)  # 墙签转写(有=高质量需求,补录直接可用)
    gpt_candidates = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    language = Column(String(8), nullable=True)
    hit_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
