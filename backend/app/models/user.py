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
    # 只回答一件事:能不能看见 published_at IS NULL 的馆。不发权益、不给额度。
    # 是 DB 列不是环境变量:验收付费链路的测试号是消耗品,换号一条 SQL,不用重新部署。
    can_preview = Column(Boolean, default=False, server_default="false", nullable=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"
