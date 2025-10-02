"""Create recognition_results table

Revision ID: 001_initial
Revises:
Create Date: 2025-10-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create recognition_results table"""
    op.create_table(
        'recognition_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('image_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('artwork_name', sa.String(255), nullable=False),
        sa.Column('artist', sa.String(255), nullable=False),
        sa.Column('period', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
    )

    # Create indexes
    op.create_index(
        'ix_recognition_results_id',
        'recognition_results',
        ['id']
    )
    op.create_index(
        'ix_recognition_results_image_hash',
        'recognition_results',
        ['image_hash'],
        unique=True
    )
    op.create_index(
        'ix_recognition_results_timestamp',
        'recognition_results',
        ['timestamp']
    )
    op.create_index(
        'ix_recognition_results_hash_timestamp',
        'recognition_results',
        ['image_hash', 'timestamp']
    )


def downgrade() -> None:
    """Drop recognition_results table"""
    op.drop_index('ix_recognition_results_hash_timestamp', table_name='recognition_results')
    op.drop_index('ix_recognition_results_timestamp', table_name='recognition_results')
    op.drop_index('ix_recognition_results_image_hash', table_name='recognition_results')
    op.drop_index('ix_recognition_results_id', table_name='recognition_results')
    op.drop_table('recognition_results')
