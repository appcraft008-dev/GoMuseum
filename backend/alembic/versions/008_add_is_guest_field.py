"""Add is_guest field to users table for guest mode

Revision ID: 008_add_is_guest_field
Revises: 007_allow_null_email
Create Date: 2025-10-17

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "008_add_is_guest_field"
down_revision = "007_allow_null_email"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("users", "is_guest")
