"""User model for authentication"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class User(Base):
    """User model for authentication and profile management"""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=True, index=True)
    username = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=True)  # NULL for OAuth users
    avatar_url = Column(String(500), nullable=True)

    # OAuth provider IDs
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    apple_id = Column(String(255), unique=True, nullable=True, index=True)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_guest = Column(Boolean, default=False, nullable=False)  # Guest user flag
    email_verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"
