"""
AI Service Log Model
SQLAlchemy model for tracking AI service calls and performance
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime


class AIServiceLog(Base):
    """
    Model for tracking AI service calls and performance metrics

    Attributes:
        id: Unique identifier (UUID)
        recognition_id: Foreign key to recognition_results table
        strategy_used: AI strategy used (openai|claude|local|manual)
        response_time: Response time in seconds
        tokens_used: Number of tokens consumed by the AI service
        cost: Cost of the AI call in USD
        error_message: Error message if the call failed (nullable)
        timestamp: When the AI call was made
    """

    __tablename__ = "ai_service_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    recognition_id = Column(
        UUID(as_uuid=True),
        ForeignKey('recognition_results.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    strategy_used = Column(String(20), nullable=False)
    response_time = Column(Float, nullable=False)  # seconds
    tokens_used = Column(Integer, nullable=True)  # null for local/manual strategies
    cost = Column(Float, default=0.0, nullable=False)  # USD
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship to RecognitionResult
    recognition = relationship("RecognitionResult", backref="ai_logs")

    # Add constraints and indexes
    __table_args__ = (
        # Data integrity constraints
        CheckConstraint(
            "strategy_used IN ('openai', 'claude', 'local', 'manual')",
            name='check_valid_strategy'
        ),
        CheckConstraint('response_time >= 0', name='check_response_time_positive'),
        CheckConstraint('tokens_used >= 0 OR tokens_used IS NULL', name='check_tokens_positive'),
        CheckConstraint('cost >= 0', name='check_cost_positive'),
        CheckConstraint('timestamp <= NOW()', name='check_timestamp_not_future'),
        # Performance indexes
        # Index for finding logs by strategy and timestamp
        Index('ix_ai_logs_strategy_timestamp', 'strategy_used', 'timestamp'),
        # Index for analyzing recent performance
        Index('ix_ai_logs_timestamp_response', 'timestamp', 'response_time', postgresql_ops={
            'timestamp': 'DESC'
        }),
        # Partial index for errors only
        Index(
            'ix_ai_logs_errors',
            'timestamp',
            'strategy_used',
            postgresql_where=Column('error_message').isnot(None)
        ),
        # Partial index for expensive calls (>$0.01)
        Index(
            'ix_ai_logs_expensive_calls',
            'timestamp',
            'cost',
            'strategy_used',
            postgresql_where=Column('cost') > 0.01
        ),
    )

    @property
    def has_error(self) -> bool:
        """Check if the AI call resulted in an error"""
        return self.error_message is not None and len(self.error_message) > 0

    @property
    def is_successful(self) -> bool:
        """Check if the AI call was successful"""
        return not self.has_error

    def __repr__(self) -> str:
        status = "ERROR" if self.has_error else "SUCCESS"
        return (
            f"<AIServiceLog(id={self.id}, strategy={self.strategy_used}, "
            f"status={status}, time={self.response_time:.3f}s, cost=${self.cost:.4f})>"
        )

    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": str(self.id),
            "recognition_id": str(self.recognition_id),
            "strategy_used": self.strategy_used,
            "response_time": self.response_time,
            "tokens_used": self.tokens_used,
            "cost": self.cost,
            "error_message": self.error_message,
            "has_error": self.has_error,
            "is_successful": self.is_successful,
            "timestamp": self.timestamp.isoformat(),
        }
