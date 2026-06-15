"""User schemas for API validation"""

from datetime import datetime
from typing import Optional

from pydantic import UUID4, BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema"""

    email: Optional[EmailStr] = None
    username: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user registration"""

    password: str


class UserUpdate(BaseModel):
    """Schema for user profile update"""

    username: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response"""

    id: UUID4
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True
