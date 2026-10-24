"""Authentication schemas"""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    """Login request schema"""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request schema"""

    email: EmailStr
    # 与重置密码(auth.py new_password)同一条规则;登录不校验长度,老账号照常可登
    password: str = Field(min_length=8, max_length=128)
    username: str | None = None


class TokenResponse(BaseModel):
    """Token response schema"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""

    refresh_token: str


class TokenData(BaseModel):
    """Token payload data"""

    user_id: str
    email: str


class OAuthRequest(BaseModel):
    """OAuth authentication request"""

    id_token: str  # ID token from OAuth provider
    username: str | None = None  # Optional username for first-time users
