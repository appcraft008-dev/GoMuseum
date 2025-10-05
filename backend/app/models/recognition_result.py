"""
Recognition Result Model
SQLAlchemy model for storing artwork recognition results
"""

from sqlalchemy import Column, String, Float, DateTime, Text, Index, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid


class RecognitionResult(Base):
    """
    Model for storing artwork recognition results

    Attributes:
        id: Unique identifier (UUID)
        image_hash: SHA256 hash of the image (for deduplication)
        artwork_name: Name of the recognized artwork
        artist: Artist who created the artwork
        period: Historical period of the artwork
        description: Detailed description of the artwork
        confidence: Confidence score from AI model (0.0 to 1.0)
        timestamp: When the recognition was performed
    """

    __tablename__ = "recognition_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    image_hash = Column(String(64), unique=True, index=True, nullable=False)
    artwork_name = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=False)
    period = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Create composite index for common queries
    __table_args__ = (
        Index("ix_recognition_results_hash_timestamp", "image_hash", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<RecognitionResult(id={self.id}, artwork={self.artwork_name}, "
            f"confidence={self.confidence})>"
        )

    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": str(self.id),
            "image_hash": self.image_hash,
            "artwork_name": self.artwork_name,
            "artist": self.artist,
            "period": self.period,
            "description": self.description,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }
