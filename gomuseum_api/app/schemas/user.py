from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: Optional[EmailStr] = Field(None, description="User email address")
    username: Optional[str] = Field(None, max_length=100, description="Username")
    language: str = Field("zh", description="Preferred language")

class UserCreate(UserBase):
    email: EmailStr = Field(..., description="User email address")
    
    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "username": "artlover",
                "language": "zh"
            }
        }

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, max_length=100, description="Username")
    language: Optional[str] = Field(None, description="Preferred language")
    
    class Config:
        schema_extra = {
            "example": {
                "username": "artlover2024",
                "language": "en"
            }
        }

class UserResponse(UserBase):
    id: str = Field(..., description="User ID")
    subscription_type: str = Field(..., description="Subscription type")
    free_quota: int = Field(..., description="Remaining free quota")
    total_recognitions: int = Field(..., description="Total recognition count")
    is_active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_seen: Optional[datetime] = Field(None, description="Last seen timestamp")
    
    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_string(cls, v):
        if hasattr(v, '__str__'):
            return str(v)
        return v
    
    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": "uuid-string",
                "email": "user@example.com",
                "username": "artlover",
                "language": "zh",
                "subscription_type": "free",
                "free_quota": 5,
                "total_recognitions": 0,
                "is_active": True,
                "created_at": "2024-01-01T12:00:00Z",
                "last_seen": None
            }
        }

class UserQuota(BaseModel):
    user_id: str = Field(..., description="User ID")
    free_quota: int = Field(..., description="Remaining free quota")
    subscription_type: str = Field(..., description="Subscription type")
    total_recognitions: int = Field(..., description="Total recognition count")
    has_quota: bool = Field(..., description="Whether user has available quota")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "uuid-string",
                "free_quota": 3,
                "subscription_type": "free",
                "total_recognitions": 2,
                "has_quota": True
            }
        }