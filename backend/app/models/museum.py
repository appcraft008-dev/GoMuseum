"""博物馆实体。"""

import uuid

from sqlalchemy import JSON, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict

from app.core.database import Base


class Museum(Base):
    __tablename__ = "museums"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(64), unique=True, index=True, nullable=False)
    qid = Column(String(32), nullable=True)
    name_zh = Column(String(255))
    name_en = Column(String(255))
    city_zh = Column(String(128))
    city_en = Column(String(128))
    country = Column(String(8))
    # 识别 KPI 聚合(埋点滚动写入);模式抄 museum_object.attributes
    stats = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    description_i18n = Column(JSON, nullable=True)  # {lang: 叙事介绍};gate 通过才写
    cover_image_key = Column(Text, nullable=True)  # 封面(得体性筛选后固化的 R2 基础键)
    # 可见性开关兼上线日期:NULL = 准备中,只有 can_preview 账号看得到
    # (spec 2026-09-20-museum-visibility-gate)。只进不出:放出后不支持回收。
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Museum(slug={self.slug}, name_en={self.name_en})>"
