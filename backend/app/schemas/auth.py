"""Authentication schemas"""

from pydantic import BaseModel, EmailStr

from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    """Login request schema"""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request schema"""

    email: EmailStr
    password: str
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
