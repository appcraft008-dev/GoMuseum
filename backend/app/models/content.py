"""讲解内容：SectionType（tab 词表）+ CategorySection（类→tab 映射）+ ObjectContentSection（实际内容）。"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SectionType(Base):
    __tablename__ = "section_types"

    code = Column(
        String(32), primary_key=True
    )  # overview | artist | background | analysis | significance | facts
    label_zh = Column(String(64))
    label_en = Column(String(64))
    icon = Column(String(64), nullable=True)
    default_sort = Column(Integer, default=0)


class CategorySection(Base):
    __tablename__ = "category_sections"

    category = Column(String(32), primary_key=True)
    section_code = Column(
        String(32), ForeignKey("section_types.code"), primary_key=True
    )
    sort_order = Column(Integer, default=0)


class ObjectContentSection(Base):
    __tablename__ = "object_content_sections"
    __table_args__ = (
        UniqueConstraint(
            "object_id", "language", "section_code", name="uq_content_obj_lang_section"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id = Column(
        UUID(as_uuid=True), ForeignKey("museum_objects.id"), nullable=False, index=True
    )
    language = Column(String(8), nullable=False)
    section_code = Column(String(32), ForeignKey("section_types.code"), nullable=False)
    body = Column(Text)
    audio_key = Column(Text, nullable=True)
    status = Column(String(16), default="published")  # draft | published | needs_review
    model = Column(String(64), nullable=True)
    source = Column(String(32), default="ai_generated")  # ai_generated | manual
    generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ObjectContentSection(object_id={self.object_id}, "
            f"language={self.language}, section_code={self.section_code})>"
        )
