"""Optimize recognition_results indexes and add constraints

Revision ID: 002_optimize_indexes
Revises: 001_initial
Create Date: 2025-10-02 00:00:00.000000

Purpose:
- Add composite indexes for common query patterns
- Add partial indexes for high-value queries
- Add GIN index for full-text search on description
- Add CHECK constraints for data integrity
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_optimize_indexes"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes and constraints to recognition_results table"""

    # Add CHECK constraints for data integrity
    # Confidence must be between 0.0 and 1.0
    op.create_check_constraint(
        "check_confidence_range",
        "recognition_results",
        "confidence >= 0.0 AND confidence <= 1.0",
    )

    # Image hash must be exactly 64 characters (SHA256)
    op.create_check_constraint(
        "check_image_hash_length", "recognition_results", "LENGTH(image_hash) = 64"
    )

    # Timestamp cannot be in the future
    op.create_check_constraint(
        "check_timestamp_not_future", "recognition_results", "timestamp <= NOW()"
    )

    # Note: Using regular CREATE INDEX instead of CONCURRENTLY
    # because CONCURRENTLY cannot run inside a transaction block
    # For production deployments with existing data, run these CONCURRENTLY manually

    # Composite indexes for common query patterns
    # Query pattern: Get recent high-confidence recognitions
    op.create_index(
        "ix_recognition_recent_confidence",
        "recognition_results",
        ["timestamp", "confidence"],
        postgresql_ops={"timestamp": "DESC", "confidence": "DESC"},
    )

    # Query pattern: Search by artist and period
    op.create_index(
        "ix_recognition_artist_period", "recognition_results", ["artist", "period"]
    )

    # Query pattern: Search by artwork name
    op.create_index(
        "ix_recognition_artwork_name", "recognition_results", ["artwork_name"]
    )

    # Partial indexes for high-value queries
    # Index for high-confidence results (confidence >= 0.8)
    op.execute("""
        CREATE INDEX ix_recognition_high_confidence
        ON recognition_results (timestamp DESC, confidence DESC)
        WHERE confidence >= 0.8
    """)

    # Note: Removed the 24-hour partial index because NOW() is not IMMUTABLE
    # and cannot be used in index predicates. Use the regular timestamp index instead.

    # GIN index for full-text search on description (supports multiple languages)
    # Create a text search configuration column first
    op.execute("""
        ALTER TABLE recognition_results
        ADD COLUMN description_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('english', description)) STORED
    """)

    # Create GIN index on the tsvector column
    op.execute("""
        CREATE INDEX ix_recognition_description_fts
        ON recognition_results USING GIN (description_tsv)
    """)

    # Composite index for artist search with timestamp ordering
    op.create_index(
        "ix_recognition_artist_timestamp",
        "recognition_results",
        ["artist", "timestamp"],
        postgresql_ops={"timestamp": "DESC"},
    )


def downgrade() -> None:
    """Remove performance indexes and constraints"""

    # Drop indexes (in reverse order)
    op.drop_index("ix_recognition_artist_timestamp", table_name="recognition_results")
    op.drop_index("ix_recognition_description_fts", table_name="recognition_results")

    # Drop the generated tsvector column
    op.execute("""
        ALTER TABLE recognition_results
        DROP COLUMN description_tsv
    """)

    op.drop_index("ix_recognition_high_confidence", table_name="recognition_results")
    op.drop_index("ix_recognition_artwork_name", table_name="recognition_results")
    op.drop_index("ix_recognition_artist_period", table_name="recognition_results")
    op.drop_index("ix_recognition_recent_confidence", table_name="recognition_results")

    # Drop CHECK constraints
    op.drop_constraint(
        "check_timestamp_not_future", "recognition_results", type_="check"
    )
    op.drop_constraint("check_image_hash_length", "recognition_results", type_="check")
    op.drop_constraint("check_confidence_range", "recognition_results", type_="check")
