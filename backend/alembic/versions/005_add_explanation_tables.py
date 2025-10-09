"""add explanation tables

Revision ID: 005
Revises: 004
Create Date: 2024-10-03 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_add_explanation_tables'
down_revision: Union[str, None] = '004_fix_timestamp_default'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create explanations and explanation_audios tables"""

    # Create explanations table
    op.create_table(
        'explanations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recognition_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('artwork_name', sa.String(length=255), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('audio_url', sa.String(length=512), nullable=True),
        sa.Column('audio_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['recognition_id'], ['recognition_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for explanations
    op.create_index('ix_explanation_artwork_lang', 'explanations', ['artwork_name', 'language'], unique=True)
    op.create_index('ix_explanation_hash', 'explanations', ['content_hash'], unique=False)
    op.create_index('ix_explanation_timestamp', 'explanations', ['timestamp'], unique=False)
    op.create_index(op.f('ix_explanations_artwork_name'), 'explanations', ['artwork_name'], unique=False)
    op.create_index(op.f('ix_explanations_language'), 'explanations', ['language'], unique=False)

    # Create explanation_audios table
    op.create_table(
        'explanation_audios',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('explanation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audio_url', sa.String(length=512), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('voice', sa.String(length=50), nullable=True, server_default='alloy'),
        sa.Column('model', sa.String(length=50), nullable=True, server_default='tts-1'),
        sa.Column('speed', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['explanation_id'], ['explanations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Drop explanations and explanation_audios tables"""

    op.drop_table('explanation_audios')

    op.drop_index(op.f('ix_explanations_language'), table_name='explanations')
    op.drop_index(op.f('ix_explanations_artwork_name'), table_name='explanations')
    op.drop_index('ix_explanation_timestamp', table_name='explanations')
    op.drop_index('ix_explanation_hash', table_name='explanations')
    op.drop_index('ix_explanation_artwork_lang', table_name='explanations')

    op.drop_table('explanations')
