"""Create recognition_stats and ai_service_logs tables

Revision ID: 003_create_stats_tables
Revises: 002_optimize_indexes
Create Date: 2025-10-02 01:00:00.000000

Purpose:
- Create recognition_stats table for daily performance metrics
- Create ai_service_logs table for AI service call tracking
- Add appropriate indexes and constraints
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_create_stats_tables"
down_revision: Union[str, None] = "002_optimize_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create statistics and logging tables"""

    # Create recognition_stats table
    op.create_table(
        "recognition_stats",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("total_requests", sa.Integer(), default=0, nullable=False),
        sa.Column("cache_hits", sa.Integer(), default=0, nullable=False),
        sa.Column("cache_misses", sa.Integer(), default=0, nullable=False),
        sa.Column("avg_response_time", sa.Float(), nullable=True),
        sa.Column("p95_response_time", sa.Float(), nullable=True),
        sa.Column("total_ai_costs", sa.Float(), default=0.0, nullable=False),
    )

    # Add indexes for recognition_stats
    op.create_index("ix_recognition_stats_id", "recognition_stats", ["id"])
    op.create_index(
        "ix_recognition_stats_date", "recognition_stats", ["date"], unique=True
    )
    op.execute("""
        CREATE INDEX ix_recognition_stats_date_desc
        ON recognition_stats (date DESC)
    """)

    # Add CHECK constraints for recognition_stats
    op.create_check_constraint(
        "check_total_requests_positive", "recognition_stats", "total_requests >= 0"
    )
    op.create_check_constraint(
        "check_cache_hits_positive", "recognition_stats", "cache_hits >= 0"
    )
    op.create_check_constraint(
        "check_cache_misses_positive", "recognition_stats", "cache_misses >= 0"
    )
    op.create_check_constraint(
        "check_cache_sum_equals_total",
        "recognition_stats",
        "cache_hits + cache_misses = total_requests",
    )
    op.create_check_constraint(
        "check_avg_response_time_positive",
        "recognition_stats",
        "avg_response_time >= 0",
    )
    op.create_check_constraint(
        "check_p95_response_time_positive",
        "recognition_stats",
        "p95_response_time >= 0",
    )
    op.create_check_constraint(
        "check_ai_costs_positive", "recognition_stats", "total_ai_costs >= 0"
    )
    op.create_check_constraint(
        "check_date_not_future", "recognition_stats", "date <= CURRENT_DATE"
    )

    # Create ai_service_logs table
    op.create_table(
        "ai_service_logs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "recognition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recognition_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("strategy_used", sa.String(20), nullable=False),
        sa.Column("response_time", sa.Float(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Float(), default=0.0, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )

    # Add indexes for ai_service_logs
    op.create_index("ix_ai_service_logs_id", "ai_service_logs", ["id"])
    op.create_index(
        "ix_ai_service_logs_recognition_id", "ai_service_logs", ["recognition_id"]
    )
    op.create_index("ix_ai_service_logs_timestamp", "ai_service_logs", ["timestamp"])

    # Composite index for strategy + timestamp queries
    op.execute("""
        CREATE INDEX ix_ai_logs_strategy_timestamp
        ON ai_service_logs (strategy_used, timestamp)
    """)

    # Composite index for timestamp + response time (for performance analysis)
    op.execute("""
        CREATE INDEX ix_ai_logs_timestamp_response
        ON ai_service_logs (timestamp DESC, response_time)
    """)

    # Partial index for errors only
    op.execute("""
        CREATE INDEX ix_ai_logs_errors
        ON ai_service_logs (timestamp, strategy_used)
        WHERE error_message IS NOT NULL
    """)

    # Partial index for expensive calls (>$0.01)
    op.execute("""
        CREATE INDEX ix_ai_logs_expensive_calls
        ON ai_service_logs (timestamp, cost, strategy_used)
        WHERE cost > 0.01
    """)

    # Add CHECK constraints for ai_service_logs
    op.create_check_constraint(
        "check_valid_strategy",
        "ai_service_logs",
        "strategy_used IN ('openai', 'claude', 'local', 'manual')",
    )
    op.create_check_constraint(
        "check_response_time_positive", "ai_service_logs", "response_time >= 0"
    )
    op.create_check_constraint(
        "check_tokens_positive",
        "ai_service_logs",
        "tokens_used >= 0 OR tokens_used IS NULL",
    )
    op.create_check_constraint("check_cost_positive", "ai_service_logs", "cost >= 0")
    op.create_check_constraint(
        "check_timestamp_not_future", "ai_service_logs", "timestamp <= NOW()"
    )


def downgrade() -> None:
    """Drop statistics and logging tables"""

    # Drop ai_service_logs table and its indexes/constraints
    op.drop_constraint("check_timestamp_not_future", "ai_service_logs", type_="check")
    op.drop_constraint("check_cost_positive", "ai_service_logs", type_="check")
    op.drop_constraint("check_tokens_positive", "ai_service_logs", type_="check")
    op.drop_constraint("check_response_time_positive", "ai_service_logs", type_="check")
    op.drop_constraint("check_valid_strategy", "ai_service_logs", type_="check")

    op.drop_index("ix_ai_logs_expensive_calls", table_name="ai_service_logs")
    op.drop_index("ix_ai_logs_errors", table_name="ai_service_logs")
    op.drop_index("ix_ai_logs_timestamp_response", table_name="ai_service_logs")
    op.drop_index("ix_ai_logs_strategy_timestamp", table_name="ai_service_logs")
    op.drop_index("ix_ai_service_logs_timestamp", table_name="ai_service_logs")
    op.drop_index("ix_ai_service_logs_recognition_id", table_name="ai_service_logs")
    op.drop_index("ix_ai_service_logs_id", table_name="ai_service_logs")

    op.drop_table("ai_service_logs")

    # Drop recognition_stats table and its indexes/constraints
    op.drop_constraint("check_date_not_future", "recognition_stats", type_="check")
    op.drop_constraint("check_ai_costs_positive", "recognition_stats", type_="check")
    op.drop_constraint(
        "check_p95_response_time_positive", "recognition_stats", type_="check"
    )
    op.drop_constraint(
        "check_avg_response_time_positive", "recognition_stats", type_="check"
    )
    op.drop_constraint(
        "check_cache_sum_equals_total", "recognition_stats", type_="check"
    )
    op.drop_constraint(
        "check_cache_misses_positive", "recognition_stats", type_="check"
    )
    op.drop_constraint("check_cache_hits_positive", "recognition_stats", type_="check")
    op.drop_constraint(
        "check_total_requests_positive", "recognition_stats", type_="check"
    )

    op.drop_index("ix_recognition_stats_date_desc", table_name="recognition_stats")
    op.drop_index("ix_recognition_stats_date", table_name="recognition_stats")
    op.drop_index("ix_recognition_stats_id", table_name="recognition_stats")

    op.drop_table("recognition_stats")
