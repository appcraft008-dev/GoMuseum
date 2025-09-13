from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from datetime import timedelta
from typing import Optional

from app.core.database import get_db
from app.core.auth import (
    create_access_token, create_refresh_token, verify_token, 
    verify_password, get_password_hash, get_current_user, security,
    AuthenticationError, standard_rate_limit
)
from app.core.token_manager import blacklist_token
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.user import UserResponse
from app.schemas.common import success_response, error_response

router = APIRouter()
logger = get_logger(__name__)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    username: Optional[str] = Field(None, max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)


@router.post("/auth/register", response_model=LoginResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(standard_rate_limit)
):
    """User registration endpoint"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "user_exists", "message": "User with this email already exists"}
            )
        
        # Create new user
        password_hash = get_password_hash(request.password)
        new_user = User(
            email=request.email,
            username=request.username,
            password_hash=password_hash,
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Create tokens
        access_token = create_access_token(
            data={"sub": str(new_user.id), "email": new_user.email}
        )
        refresh_token = create_refresh_token(str(new_user.id))
        
        logger.info(f"New user registered: {new_user.email}")
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,  # 1 hour
            user=UserResponse.model_validate(new_user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "registration_failed", "message": "Registration service temporarily unavailable"}
        )


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(standard_rate_limit)
):
    """User login endpoint"""
    try:
        # Find user by email
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            logger.warning(f"Login attempt with non-existent email: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_credentials", "message": "Invalid email or password"}
            )
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login attempt with inactive account: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "account_disabled", "message": "Account is disabled"}
            )
        
        # Check if user has password set
        if not user.password_hash:
            logger.warning(f"User has no password set: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_credentials", "message": "Invalid email or password"}
            )
        
        # Verify password
        if not verify_password(request.password, user.password_hash):
            logger.warning(f"Invalid password for user: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_credentials", "message": "Invalid email or password"}
            )
        
        # Create tokens
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        refresh_token = create_refresh_token(str(user.id))
        
        # Update last seen
        from datetime import datetime, timezone
        user.last_seen = datetime.now(timezone.utc)
        db.commit()
        
        logger.info(f"User logged in successfully: {user.email}")
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,  # 1 hour
            user=UserResponse.model_validate(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "login_failed", "message": "Login service temporarily unavailable"}
        )


@router.post("/auth/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(standard_rate_limit)
):
    """Refresh access token"""
    try:
        # Verify refresh token
        payload = await verify_token(request.refresh_token)
        
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token: missing user ID")
        
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        
        # Create new access token
        access_token = create_access_token(
            data={"sub": user_id, "email": user.email}
        )
        
        logger.info(f"Token refreshed for user: {user.email}")
        
        return success_response({
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 3600
        })
        
    except AuthenticationError as e:
        logger.warning(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_refresh_token", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "refresh_failed", "message": "Token refresh service unavailable"}
        )


@router.post("/auth/logout")
async def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    current_user: dict = Depends(get_current_user)
):
    """User logout endpoint"""
    try:
        if credentials:
            # Add token to blacklist using new token manager
            await blacklist_token(credentials.credentials, "logout")
        
        logger.info(f"User logged out: {current_user['email']}")
        
        return success_response({"message": "Logged out successfully"})
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}", exc_info=True)
        return success_response({"message": "Logged out successfully"})  # Always succeed


@router.get("/auth/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authentication_required", "message": "Authentication required"}
        )
    
    try:
        # Get fresh user data
        user = db.query(User).filter(User.id == current_user["id"]).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "user_not_found", "message": "User not found"}
            )
        
        return UserResponse.model_validate(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "get_user_failed", "message": "Unable to retrieve user information"}
        )


@router.post("/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: bool = Depends(standard_rate_limit)
):
    """Change user password"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authentication_required", "message": "Authentication required"}
        )
    
    try:
        # Get user from database
        user = db.query(User).filter(User.id == current_user["id"]).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "user_not_found", "message": "User not found"}
            )
        
        # Verify current password
        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "no_password_set", "message": "No password currently set"}
            )
        
        if not verify_password(request.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_current_password", "message": "Current password is incorrect"}
            )
        
        # Hash and save new password
        user.password_hash = get_password_hash(request.new_password)
        db.commit()
        
        logger.info(f"Password changed for user: {user.email}")
        
        return success_response({"message": "Password changed successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "change_password_failed", "message": "Unable to change password"}
        )


@router.get("/auth/verify-token")
async def verify_token_endpoint(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Verify if current token is valid"""
    if not current_user:
        return {"valid": False, "message": "Invalid or expired token"}
    
    return success_response({
        "valid": True,
        "user_id": current_user["id"],
        "email": current_user["email"]
    })