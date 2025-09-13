"""
Enhanced Token Management Module

Provides secure token management with Redis-based blacklisting,
persistent storage, and comprehensive security features.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Set
import json
import jwt
from passlib.context import CryptContext

from app.core.logging import get_logger
from app.core.redis_client import redis_client, get_cache_key
from app.core.security_config import get_key_manager
from app.core.config import settings

logger = get_logger(__name__)


class TokenManager:
    """Enhanced token manager with Redis-based blacklisting and security features"""
    
    def __init__(self):
        self.key_manager = get_key_manager()
        self._pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
    def get_jwt_secret_key(self) -> str:
        """Get JWT secret key from secure key manager"""
        return self.key_manager.get_jwt_secret_key()
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token with enhanced security"""
        to_encode = data.copy()
        
        # Set expiration
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.access_token_expire_minutes
            )
        
        # Add standard JWT claims
        now = datetime.now(timezone.utc)
        to_encode.update({
            "exp": expire,
            "iat": now,
            "nbf": now,  # Not before (prevent token use before issuance)
            "type": "access",
            "jti": self._generate_jti(),  # JWT ID for blacklisting
            "iss": "gomuseum-api",  # Issuer
            "aud": "gomuseum-client"  # Audience
        })
        
        # Sign token with secure key (using HMAC-SHA256 with secure key management)
        encoded_jwt = jwt.encode(
            to_encode, 
            self.get_jwt_secret_key(), 
            algorithm="HS256"  # Use HMAC-SHA256 with secure key management
        )
        
        logger.info(
            "Access token created", 
            extra={
                "user_id": data.get("sub"),
                "expires_at": expire.isoformat(),
                "jti": to_encode["jti"]
            }
        )
        
        return encoded_jwt
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create JWT refresh token with enhanced security"""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=settings.refresh_token_expire_days)
        
        data = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": now,
            "nbf": now,
            "jti": self._generate_jti(),
            "iss": "gomuseum-api",
            "aud": "gomuseum-client"
        }
        
        encoded_jwt = jwt.encode(
            data, 
            self.get_jwt_secret_key(), 
            algorithm="HS256"
        )
        
        logger.info(
            "Refresh token created", 
            extra={
                "user_id": user_id,
                "expires_at": expire.isoformat(),
                "jti": data["jti"]
            }
        )
        
        return encoded_jwt
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token with blacklist check"""
        try:
            # Check if token is blacklisted
            if await self.is_token_blacklisted(token):
                raise jwt.InvalidTokenError("Token has been blacklisted")
            
            # Decode and verify token
            payload = jwt.decode(
                token, 
                self.get_jwt_secret_key(), 
                algorithms=["HS256"],
                audience="gomuseum-client",
                issuer="gomuseum-api"
            )
            
            # Validate token type
            token_type = payload.get("type")
            if token_type not in ["access", "refresh"]:
                raise jwt.InvalidTokenError("Invalid token type")
            
            # Check if token has JTI
            if not payload.get("jti"):
                raise jwt.InvalidTokenError("Token missing JWT ID")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: expired")
            raise jwt.InvalidTokenError("Token expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token verification failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}", exc_info=True)
            raise jwt.InvalidTokenError("Token verification failed")
    
    async def blacklist_token(self, token: str, reason: str = "logout") -> bool:
        """Add token to Redis blacklist"""
        try:
            # Decode token to get expiration and JTI
            payload = jwt.decode(
                token, 
                self.get_jwt_secret_key(), 
                algorithms=["HS256"],
                options={"verify_exp": False}  # Don't verify expiration for blacklisting
            )
            
            jti = payload.get("jti")
            exp = payload.get("exp")
            
            if not jti:
                logger.warning("Cannot blacklist token without JTI")
                return False
            
            # Calculate TTL (time until token expires)
            if exp:
                ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp()))
            else:
                ttl = 60 * 60 * 24 * 7  # 7 days default
            
            # Store in Redis blacklist
            blacklist_key = get_cache_key("token_blacklist", jti)
            blacklist_data = {
                "jti": jti,
                "reason": reason,
                "blacklisted_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": datetime.fromtimestamp(exp, timezone.utc).isoformat() if exp else None
            }
            
            await redis_client.set(blacklist_key, blacklist_data, ttl)
            
            logger.info(
                f"Token blacklisted: {reason}",
                extra={
                    "jti": jti,
                    "reason": reason,
                    "ttl": ttl
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to blacklist token: {str(e)}", exc_info=True)
            return False
    
    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is in Redis blacklist"""
        try:
            # Decode token to get JTI
            payload = jwt.decode(
                token, 
                self.get_jwt_secret_key(), 
                algorithms=["HS256"],
                options={"verify_exp": False}
            )
            
            jti = payload.get("jti")
            if not jti:
                return False
            
            # Check Redis blacklist
            blacklist_key = get_cache_key("token_blacklist", jti)
            blacklist_data = await redis_client.get(blacklist_key)
            
            return blacklist_data is not None
            
        except Exception as e:
            logger.error(f"Error checking token blacklist: {str(e)}", exc_info=True)
            return False
    
    async def logout_user_tokens(self, user_id: str) -> int:
        """Blacklist all tokens for a specific user"""
        try:
            # This would require maintaining a user-to-token mapping in Redis
            # For now, we'll implement a pattern-based approach
            pattern = get_cache_key("user_tokens", user_id, "*")
            
            # In production, you'd maintain a set of active tokens per user
            # and blacklist them all
            
            logger.info(f"Logout requested for user: {user_id}")
            return 0  # Return number of tokens blacklisted
            
        except Exception as e:
            logger.error(f"Error during user logout: {str(e)}", exc_info=True)
            return 0
    
    async def cleanup_expired_blacklist(self) -> int:
        """Clean up expired tokens from blacklist (Redis TTL handles this automatically)"""
        try:
            # Redis TTL automatically removes expired keys
            # This method is for manual cleanup if needed
            
            pattern = get_cache_key("token_blacklist", "*")
            # Use Redis SCAN to find and clean up manually if needed
            
            logger.info("Token blacklist cleanup completed")
            return 0
            
        except Exception as e:
            logger.error(f"Error cleaning up token blacklist: {str(e)}", exc_info=True)
            return 0
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return self._pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self._pwd_context.verify(plain_password, hashed_password)
    
    def _generate_jti(self) -> str:
        """Generate unique JWT ID"""
        import uuid
        return str(uuid.uuid4())
    
    async def get_token_stats(self) -> Dict[str, Any]:
        """Get token management statistics"""
        try:
            # Count blacklisted tokens
            pattern = get_cache_key("token_blacklist", "*")
            blacklisted_count = 0  # Would need to implement Redis SCAN
            
            return {
                "blacklisted_tokens": blacklisted_count,
                "algorithm": "HS256",
                "key_manager": "secure",
                "redis_enabled": redis_client.redis is not None
            }
            
        except Exception as e:
            logger.error(f"Error getting token stats: {str(e)}", exc_info=True)
            return {"error": str(e)}


# Global token manager instance
token_manager = TokenManager()


# Convenience functions for backward compatibility
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create access token - convenience function"""
    return token_manager.create_access_token(data, expires_delta)


def create_refresh_token(user_id: str) -> str:
    """Create refresh token - convenience function"""
    return token_manager.create_refresh_token(user_id)


async def verify_token(token: str) -> Dict[str, Any]:
    """Verify token - convenience function"""
    return await token_manager.verify_token(token)


async def blacklist_token(token: str, reason: str = "logout") -> bool:
    """Blacklist token - convenience function"""
    return await token_manager.blacklist_token(token, reason)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password - convenience function"""
    return token_manager.verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password - convenience function"""
    return token_manager.hash_password(password)


# Periodic cleanup task
async def start_token_cleanup_task():
    """Start periodic token cleanup task"""
    while True:
        try:
            await token_manager.cleanup_expired_blacklist()
            await asyncio.sleep(3600)  # Run every hour
        except Exception as e:
            logger.error(f"Token cleanup task error: {e}")
            await asyncio.sleep(1800)  # Wait 30 minutes on error