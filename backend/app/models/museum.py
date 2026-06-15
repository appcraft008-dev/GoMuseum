"""博物馆实体。"""

import uuid

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Museum(slug={self.slug}, name_en={self.name_en})>"
