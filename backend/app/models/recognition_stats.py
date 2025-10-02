"""
Recognition Statistics Model
SQLAlchemy model for storing daily performance statistics
"""

from sqlalchemy import Column, Integer, Float, Date, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import date


class RecognitionStats(Base):
    """
    Model for storing daily recognition performance statistics

    Attributes:
        id: Unique identifier (UUID)
        date: Date of the statistics (unique per day)
        total_requests: Total number of recognition requests
        cache_hits: Number of cache hits (found in database)
        cache_misses: Number of cache misses (required AI call)
        avg_response_time: Average response time in seconds
        p95_response_time: 95th percentile response time in seconds
        total_ai_costs: Total AI API costs in USD
    """

    __tablename__ = "recognition_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    total_requests = Column(Integer, default=0, nullable=False)
    cache_hits = Column(Integer, default=0, nullable=False)
    cache_misses = Column(Integer, default=0, nullable=False)
    avg_response_time = Column(Float, nullable=True)  # seconds
    p95_response_time = Column(Float, nullable=True)  # seconds
    total_ai_costs = Column(Float, default=0.0, nullable=False)  # USD

    # Add constraints to ensure data integrity
    __table_args__ = (
        CheckConstraint('total_requests >= 0', name='check_total_requests_positive'),
        CheckConstraint('cache_hits >= 0', name='check_cache_hits_positive'),
        CheckConstraint('cache_misses >= 0', name='check_cache_misses_positive'),
        CheckConstraint('cache_hits + cache_misses = total_requests', name='check_cache_sum_equals_total'),
        CheckConstraint('avg_response_time >= 0', name='check_avg_response_time_positive'),
        CheckConstraint('p95_response_time >= 0', name='check_p95_response_time_positive'),
        CheckConstraint('total_ai_costs >= 0', name='check_ai_costs_positive'),
        CheckConstraint('date <= CURRENT_DATE', name='check_date_not_future'),
        # Create index for date range queries (most recent first)
        Index('ix_recognition_stats_date_desc', 'date', postgresql_ops={'date': 'DESC'}),
    )

    @property
    def cache_hit_rate(self) -> float:
        """
        Calculate cache hit rate as a percentage

        Returns:
            float: Cache hit rate (0.0 to 1.0)
        """
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    @property
    def cache_miss_rate(self) -> float:
        """
        Calculate cache miss rate as a percentage

        Returns:
            float: Cache miss rate (0.0 to 1.0)
        """
        return 1.0 - self.cache_hit_rate

    def __repr__(self) -> str:
        return (
            f"<RecognitionStats(date={self.date}, requests={self.total_requests}, "
            f"hit_rate={self.cache_hit_rate:.2%})>"
        )

    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": str(self.id),
            "date": self.date.isoformat(),
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "cache_miss_rate": self.cache_miss_rate,
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
            "total_ai_costs": self.total_ai_costs,
        }
