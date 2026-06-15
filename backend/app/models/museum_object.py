"""通用展品（MuseumObject）+ 展品图片（ObjectImage，一对多）。"""

import uuid

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict

from app.core.database import Base


class MuseumObject(Base):
    __tablename__ = "museum_objects"
    __table_args__ = (
        UniqueConstraint(
            "museum_id", "inventory_number", name="uq_object_museum_inventory"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    museum_id = Column(
        UUID(as_uuid=True), ForeignKey("museums.id"), nullable=False, index=True
    )
    qid = Column(String(32), unique=True, nullable=True, index=True)  # Wikidata QID
    inventory_number = Column(String(128), nullable=True)  # 馆藏号
    category = Column(String(32), nullable=False, default="painting")
    title_zh = Column(String(512))
    title_en = Column(String(512))
    artist_zh = Column(String(255))
    artist_en = Column(String(255))
    year = Column(String(64))
    period_zh = Column(String(128))
    period_en = Column(String(128))
    popularity = Column(Integer, default=0, index=True)
    # MutableDict 让原地修改 attributes（如 obj.attributes["k"]=v）也能被 SQLAlchemy 检测到
    attributes = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), default=dict
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MuseumObject(id={self.id}, qid={self.qid}, title_en={self.title_en})>"


class ObjectImage(Base):
    __tablename__ = "object_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id = Column(
        UUID(as_uuid=True), ForeignKey("museum_objects.id"), nullable=False, index=True
    )
    role = Column(String(32), default="primary")  # primary | detail | view | back
    source_url = Column(Text)
    image_key = Column(Text, nullable=True)  # R2 自存副本 key
    license = Column(String(128), nullable=True)
    credit = Column(String(255), nullable=True)
    sort = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
