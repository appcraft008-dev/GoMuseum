"""Add User model for authentication

Revision ID: 006_add_user_auth
Revises: 005_add_explanation_tables
Create Date: 2025-10-10

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "006_add_user_auth"
down_revision = "004_fix_timestamp_default"
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        # OAuth provider IDs
        sa.Column("google_id", sa.String(255), nullable=True, unique=True),
        sa.Column("facebook_id", sa.String(255), nullable=True, unique=True),
        sa.Column("apple_id", sa.String(255), nullable=True, unique=True),
        # Account status
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_verified", sa.Boolean(), default=False, nullable=False),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )

    # Create indexes
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_google_id", "users", ["google_id"])
    op.create_index("idx_users_facebook_id", "users", ["facebook_id"])
    op.create_index("idx_users_apple_id", "users", ["apple_id"])


def downgrade():
    op.drop_index("idx_users_apple_id")
    op.drop_index("idx_users_facebook_id")
    op.drop_index("idx_users_google_id")
    op.drop_index("idx_users_email")
    op.drop_table("users")
