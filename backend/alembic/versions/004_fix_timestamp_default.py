"""Fix timestamp default to use server-side now()

Revision ID: 004_fix_timestamp_default
Revises: 003_create_stats_tables
Create Date: 2024-10-03

This migration fixes the timestamp field in recognition_results table to use
PostgreSQL's now() function instead of Python's datetime.utcnow(). This prevents
race conditions where the application timestamp might be slightly ahead of the
database's now() causing check constraint violations.

Changes:
- Update timestamp column default from client-side to server-side (now())
- This ensures timestamp <= now() check constraint never fails due to timing issues
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "004_fix_timestamp_default"
down_revision = "003_create_stats_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Change timestamp column default to use PostgreSQL's now() function
    instead of Python's datetime.utcnow()
    """
    # Note: We need to alter the column to use server_default instead of default
    # This cannot be done with simple alter_column, so we use raw SQL
    op.execute(
        """
        ALTER TABLE recognition_results
        ALTER COLUMN timestamp
        SET DEFAULT now();
    """
    )


def downgrade() -> None:
    """
    Revert timestamp column default back to no server default
    (Python application will provide the value)
    """
    op.execute(
        """
        ALTER TABLE recognition_results
        ALTER COLUMN timestamp
        DROP DEFAULT;
    """
    )
