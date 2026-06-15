"""Allow users.email to be nullable for OAuth-only accounts

Revision ID: 007_allow_null_email
Revises: 006_add_user_auth
Create Date: 2025-10-06

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "007_allow_null_email"
down_revision = "006_add_user_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade():
    # WARNING: this will fail if there are rows with NULL email values
    op.execute(
        """
        DELETE FROM users
        WHERE email IS NULL
        """
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        nullable=False,
    )
