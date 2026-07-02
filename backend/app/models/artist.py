"""作者一等实体:按 artist QID 生成一次的规范作者介绍,同作者作品复用。"""

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import JSON

from app.core.database import Base


class Artist(Base):
    __tablename__ = "artists"

    qid = Column(String(32), primary_key=True)
    name_zh = Column(String(255), nullable=True)
    name_en = Column(String(255), nullable=True)
    birth = Column(String(16), nullable=True)
    death = Column(String(16), nullable=True)
    nationality = Column(String(128), nullable=True)
    notable_works = Column(
        MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )
    bio = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )
    name_i18n = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )  # {lang: name} 多语显示名
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
