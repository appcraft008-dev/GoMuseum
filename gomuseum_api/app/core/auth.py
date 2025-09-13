from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .logging import get_logger
from .token_manager import (
    token_manager, create_access_token, create_refresh_token,
    verify_token, blacklist_token, verify_password, get_password_hash
)

logger = get_logger(__name__)

# JWT Bearer token scheme
security = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """Authentication related errors"""
    pass


class AuthorizationError(Exception):
    """Authorization related errors"""
    pass


# Token management functions are now imported from token_manager module


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """Get current authenticated user from token"""
    
    if not credentials:
        return None  # Allow anonymous access for public endpoints
    
    try:
        # Verify token with enhanced security
        payload = await verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise AuthenticationError("Invalid token: missing user ID")
        
        # Get user from database
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        
        if user is None:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User account is disabled")
        
        # Update last seen
        user.last_seen = datetime.now(timezone.utc)
        db.commit()
        
        logger.info("User authenticated successfully", extra={"user_id": user_id})
        
        return {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "subscription_type": user.subscription_type,
            "is_active": user.is_active
        }
        
    except AuthenticationError as e:
        logger.warning(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authentication_failed", "message": str(e)},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "authentication_error", "message": "Authentication service unavailable"}
        )


async def require_auth(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Require authentication for protected endpoints"""
    
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authentication_required", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return current_user


def require_subscription(subscription_types: list[str]):
    """Decorator to require specific subscription types"""
    
    def dependency(current_user: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
        user_subscription = current_user.get("subscription_type", "free")
        
        if user_subscription not in subscription_types:
            logger.warning(
                f"Insufficient subscription level",
                extra={
                    "user_id": current_user["id"],
                    "required": subscription_types,
                    "actual": user_subscription
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_subscription",
                    "message": f"Requires subscription: {' or '.join(subscription_types)}",
                    "current_subscription": user_subscription
                }
            )
        
        return current_user
    
    return dependency


# Subscription level dependencies
require_premium = require_subscription(["premium", "enterprise"])
require_enterprise = require_subscription(["enterprise"])


# Token blacklist is now handled by the enhanced token_manager with Redis
# See app.core.token_manager for the Redis-based implementation


# Rate limiting per user
class UserRateLimit:
    """Simple rate limiting per user"""
    _user_requests = {}
    
    @classmethod
    def check_rate_limit(cls, user_id: str, limit: int = 100, window: int = 3600) -> bool:
        """Check if user is within rate limit"""
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - window
        
        if user_id not in cls._user_requests:
            cls._user_requests[user_id] = []
        
        # Clean old requests
        cls._user_requests[user_id] = [
            req_time for req_time in cls._user_requests[user_id]
            if req_time > window_start
        ]
        
        # Check limit
        if len(cls._user_requests[user_id]) >= limit:
            return False
        
        # Add current request
        cls._user_requests[user_id].append(now)
        return True


def rate_limit_check(limit: int = 100, window: int = 3600):
    """Rate limiting dependency"""
    
    def dependency(
        request: Request,
        current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
    ) -> bool:
        # Use IP for anonymous users, user_id for authenticated users
        identifier = current_user["id"] if current_user else request.client.host
        
        if not UserRateLimit.check_rate_limit(identifier, limit, window):
            logger.warning(
                "Rate limit exceeded",
                extra={"identifier": identifier, "limit": limit, "window": window}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit of {limit} requests per {window} seconds exceeded"
                }
            )
        
        return True
    
    return dependency


# Common rate limits
standard_rate_limit = rate_limit_check(limit=100, window=3600)  # 100 requests per hour
recognition_rate_limit = rate_limit_check(limit=20, window=300)  # 20 recognitions per 5 minutes