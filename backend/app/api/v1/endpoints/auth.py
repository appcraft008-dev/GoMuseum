"""Authentication API endpoints"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    OAuthRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user with email and password

    - **email**: User's email address (must be unique)
    - **password**: User's password (min 8 characters recommended)
    - **username**: Optional display name

    Returns access token, refresh token, and user profile
    """
    return AuthService.register(db, payload)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password

    - **email**: User's registered email
    - **password**: User's password

    Returns access token, refresh token, and user profile
    """
    return AuthService.login(db, payload)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token

    - **refresh_token**: Valid refresh token

    Returns new access token, new refresh token, and user profile
    """
    return AuthService.refresh_token(db, request.refresh_token)


@router.get("/me", response_model=UserResponse)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Get current authenticated user profile

    Requires valid access token in Authorization header:
    `Authorization: Bearer {access_token}`

    Returns user profile information
    """
    token = credentials.credentials
    user = AuthService.get_current_user(db, token)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout current user

    Note: Since we're using stateless JWT, logout is handled client-side
    by deleting the stored tokens. This endpoint is provided for consistency.
    """
    # In a stateless JWT system, logout is handled by the client deleting tokens
    # If you want server-side token revocation, implement a token blacklist
    return None


@router.post("/google", response_model=TokenResponse)
def google_login(request: OAuthRequest, db: Session = Depends(get_db)):
    """
    Authenticate with Google Sign-In

    - **id_token**: Google ID token from the client
    - **username**: Optional username for new users

    The client should obtain the ID token using Google Sign-In SDK,
    then send it to this endpoint for verification and authentication.

    Configuration required:
    - Set GOOGLE_CLIENT_ID in backend settings
    - Configure Google OAuth 2.0 credentials in Google Cloud Console
    """
    return AuthService.oauth_google(db, request)


@router.post("/apple", response_model=TokenResponse)
def apple_login(request: OAuthRequest, db: Session = Depends(get_db)):
    """
    Authenticate with Apple Sign In

    - **id_token**: Apple ID token from the client
    - **username**: Optional username for new users

    The client should obtain the ID token using Sign in with Apple,
    then send it to this endpoint for verification and authentication.

    Configuration required:
    - Set APPLE_CLIENT_ID in backend settings
    - Configure Sign in with Apple in Apple Developer Portal
    - Implement Apple JWT token verification
    """
    return AuthService.oauth_apple(db, request)


class GuestLoginRequest(BaseModel):
    device_id: Optional[str] = None


@router.post("/guest", response_model=TokenResponse)
@limiter.limit("5/hour")
def guest_login(
    request: Request,
    payload: Optional[GuestLoginRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Login as a guest user without authentication

    Creates a temporary guest account that allows users to access the app
    without registration. Guest accounts have limited functionality.

    - No email or password required
    - Generates a random guest username
    - Returns access token and guest user profile

    Guest users can later convert to regular users by registering.
    """
    return AuthService.guest_login(db, payload.device_id if payload else None)


@router.get("/me/export")
def export_my_data(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    GDPR data portability: export all personal data as JSON

    Returns user profile and benefits records associated with the account.
    """
    token = credentials.credentials
    user = AuthService.get_current_user(db, token)
    return AuthService.export_user_data(db, user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    GDPR right to erasure / App Store account deletion requirement

    Permanently deletes the account and all associated personal data
    (profile, benefits). This action is irreversible.
    """
    token = credentials.credentials
    user = AuthService.get_current_user(db, token)
    AuthService.delete_user_account(db, user)
    return None
