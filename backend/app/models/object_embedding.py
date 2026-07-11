"""展品参考图向量(生成一次永久落库;model 字段版本化,换模型共存不冲突)。"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ObjectEmbedding(Base):
    __tablename__ = "object_embeddings"
    __table_args__ = (
        UniqueConstraint("image_id", "model", name="uq_embedding_image_model"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id = Column(
        UUID(as_uuid=True), ForeignKey("museum_objects.id"), nullable=False, index=True
    )
    image_id = Column(
        UUID(as_uuid=True), ForeignKey("object_images.id"), nullable=False, index=True
    )
    model = Column(String(64), nullable=False)
    vec = Column(LargeBinary, nullable=False)  # float32 bytes
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
