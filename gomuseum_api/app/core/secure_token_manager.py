"""
Secure Token Management with Redis-based Blacklist

Provides secure JWT token management with proper blacklisting,
refresh token rotation, and session management.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Set
import jwt
from redis import Redis
import hashlib

from app.core.logging import get_logger
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)


class SecureTokenManager:
    """Manages JWT tokens with Redis-based blacklist and session tracking"""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client or get_redis_client()
        self.token_prefix = "token:"
        self.session_prefix = "session:"
        self.blacklist_prefix = "blacklist:"
        self.refresh_prefix = "refresh:"
        
    def create_token_pair(self, user_data: Dict[str, Any], secret_key: str) -> Dict[str, str]:
        """Create access and refresh token pair with session tracking"""
        from app.core.config import settings
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        user_id = user_data.get("sub", user_data.get("id"))
        
        # Create access token
        access_payload = {
            **user_data,
            "type": "access",
            "session_id": session_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
            "jti": str(uuid.uuid4())  # JWT ID for tracking
        }
        
        # Create refresh token
        refresh_payload = {
            "sub": user_id,
            "type": "refresh", 
            "session_id": session_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            "jti": str(uuid.uuid4()),
            "rotation_count": 0  # Track refresh token rotations
        }
        
        access_token = jwt.encode(access_payload, secret_key, algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, secret_key, algorithm="HS256")
        
        # Store session info in Redis
        session_data = {
            "user_id": user_id,
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "ip_address": user_data.get("ip_address"),
            "user_agent": user_data.get("user_agent"),
            "access_jti": access_payload["jti"],
            "refresh_jti": refresh_payload["jti"]
        }
        
        # Store with expiration matching refresh token
        session_key = f"{self.session_prefix}{session_id}"
        self.redis.setex(
            session_key,
            timedelta(days=settings.refresh_token_expire_days),
            json.dumps(session_data)
        )
        
        # Store refresh token metadata for rotation tracking
        refresh_key = f"{self.refresh_prefix}{refresh_payload['jti']}"
        self.redis.setex(
            refresh_key,
            timedelta(days=settings.refresh_token_expire_days),
            json.dumps({
                "session_id": session_id,
                "rotation_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        )
        
        logger.info(f"Token pair created for user {user_id}, session {session_id}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "session_id": session_id
        }
    
    def verify_token(self, token: str, secret_key: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify token and check blacklist"""
        try:
            # Decode token
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            
            # Verify token type
            if payload.get("type") != token_type:
                raise jwt.InvalidTokenError(f"Invalid token type, expected {token_type}")
            
            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and self.is_token_blacklisted(jti):
                raise jwt.InvalidTokenError("Token has been revoked")
            
            # Check session validity
            session_id = payload.get("session_id")
            if session_id:
                session_key = f"{self.session_prefix}{session_id}"
                session_data = self.redis.get(session_key)
                
                if not session_data:
                    raise jwt.InvalidTokenError("Session expired or invalid")
                
                # Update last activity
                session = json.loads(session_data)
                session["last_activity"] = datetime.now(timezone.utc).isoformat()
                self.redis.setex(
                    session_key,
                    self.redis.ttl(session_key),  # Preserve TTL
                    json.dumps(session)
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidTokenError:
            raise
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise jwt.InvalidTokenError(f"Token validation failed: {str(e)}")
    
    def refresh_access_token(self, refresh_token: str, secret_key: str) -> Dict[str, str]:
        """Refresh access token with rotation detection"""
        from app.core.config import settings
        
        # Verify refresh token
        payload = self.verify_token(refresh_token, secret_key, token_type="refresh")
        
        jti = payload.get("jti")
        session_id = payload.get("session_id")
        user_id = payload.get("sub")
        
        # Check refresh token metadata
        refresh_key = f"{self.refresh_prefix}{jti}"
        refresh_data = self.redis.get(refresh_key)
        
        if not refresh_data:
            # Token might be reused after rotation - potential attack
            logger.warning(f"Refresh token reuse detected for user {user_id}")
            # Invalidate entire session
            self.revoke_session(session_id)
            raise jwt.InvalidTokenError("Refresh token has been rotated or revoked")
        
        refresh_meta = json.loads(refresh_data)
        rotation_count = refresh_meta.get("rotation_count", 0)
        
        # Check rotation limit
        max_rotations = 5
        if rotation_count >= max_rotations:
            logger.warning(f"Max refresh rotations reached for session {session_id}")
            self.revoke_session(session_id)
            raise jwt.InvalidTokenError("Maximum refresh token rotations exceeded")
        
        # Create new access token
        new_access_payload = {
            "sub": user_id,
            "type": "access",
            "session_id": session_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
            "jti": str(uuid.uuid4())
        }
        
        new_access_token = jwt.encode(new_access_payload, secret_key, algorithm="HS256")
        
        # Optionally rotate refresh token (for enhanced security)
        should_rotate = rotation_count > 0 and rotation_count % 3 == 0
        
        if should_rotate:
            # Create new refresh token
            new_refresh_payload = {
                "sub": user_id,
                "type": "refresh",
                "session_id": session_id,
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
                "jti": str(uuid.uuid4()),
                "rotation_count": rotation_count + 1
            }
            
            new_refresh_token = jwt.encode(new_refresh_payload, secret_key, algorithm="HS256")
            
            # Blacklist old refresh token
            self.blacklist_token(jti, ttl=timedelta(days=settings.refresh_token_expire_days))
            
            # Store new refresh token metadata
            new_refresh_key = f"{self.refresh_prefix}{new_refresh_payload['jti']}"
            self.redis.setex(
                new_refresh_key,
                timedelta(days=settings.refresh_token_expire_days),
                json.dumps({
                    "session_id": session_id,
                    "rotation_count": rotation_count + 1,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            )
            
            logger.info(f"Refresh token rotated for session {session_id}")
            
            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "rotated": True
            }
        else:
            # Update rotation count
            refresh_meta["rotation_count"] = rotation_count + 1
            self.redis.setex(
                refresh_key,
                self.redis.ttl(refresh_key),  # Preserve TTL
                json.dumps(refresh_meta)
            )
            
            return {
                "access_token": new_access_token,
                "refresh_token": refresh_token,  # Same refresh token
                "rotated": False
            }
    
    def blacklist_token(self, jti: str, ttl: Optional[timedelta] = None):
        """Add token to blacklist with TTL"""
        if not jti:
            return
        
        blacklist_key = f"{self.blacklist_prefix}{jti}"
        
        # Default TTL to 30 days if not specified
        ttl = ttl or timedelta(days=30)
        
        # Store blacklisted token with metadata
        blacklist_data = {
            "blacklisted_at": datetime.now(timezone.utc).isoformat(),
            "jti": jti
        }
        
        self.redis.setex(blacklist_key, ttl, json.dumps(blacklist_data))
        logger.info(f"Token {jti} blacklisted")
    
    def is_token_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        if not jti:
            return False
        
        blacklist_key = f"{self.blacklist_prefix}{jti}"
        return self.redis.exists(blacklist_key) > 0
    
    def revoke_session(self, session_id: str):
        """Revoke entire session and all associated tokens"""
        if not session_id:
            return
        
        session_key = f"{self.session_prefix}{session_id}"
        session_data = self.redis.get(session_key)
        
        if session_data:
            session = json.loads(session_data)
            
            # Blacklist associated tokens
            if session.get("access_jti"):
                self.blacklist_token(session["access_jti"])
            
            if session.get("refresh_jti"):
                self.blacklist_token(session["refresh_jti"])
            
            # Delete session
            self.redis.delete(session_key)
            
            logger.info(f"Session {session_id} revoked")
    
    def get_active_sessions(self, user_id: str) -> list:
        """Get all active sessions for a user"""
        sessions = []
        
        # Scan for user sessions
        cursor = 0
        pattern = f"{self.session_prefix}*"
        
        while True:
            cursor, keys = self.redis.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                session_data = self.redis.get(key)
                if session_data:
                    session = json.loads(session_data)
                    if session.get("user_id") == user_id:
                        session["session_id"] = key.replace(self.session_prefix, "")
                        sessions.append(session)
            
            if cursor == 0:
                break
        
        return sessions
    
    def revoke_all_user_sessions(self, user_id: str):
        """Revoke all sessions for a user"""
        sessions = self.get_active_sessions(user_id)
        
        for session in sessions:
            self.revoke_session(session["session_id"])
        
        logger.info(f"All sessions revoked for user {user_id}")
    
    def cleanup_expired_blacklist(self):
        """Clean up expired blacklist entries (called periodically)"""
        # Redis handles expiration automatically with TTL
        # This method is for additional cleanup if needed
        pass


class TokenRateLimiter:
    """Rate limiting for token operations"""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client or get_redis_client()
        self.prefix = "token_rate:"
    
    def check_rate_limit(self, identifier: str, operation: str, limit: int, window: int) -> bool:
        """Check if operation is within rate limit"""
        key = f"{self.prefix}{operation}:{identifier}"
        
        try:
            current = self.redis.incr(key)
            
            if current == 1:
                # Set expiration on first request
                self.redis.expire(key, window)
            
            if current > limit:
                ttl = self.redis.ttl(key)
                logger.warning(f"Rate limit exceeded for {identifier} on {operation}: {current}/{limit}, TTL: {ttl}s")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open in case of Redis issues
            return True
    
    def get_remaining_limit(self, identifier: str, operation: str, limit: int) -> int:
        """Get remaining rate limit"""
        key = f"{self.prefix}{operation}:{identifier}"
        current = self.redis.get(key)
        
        if current:
            return max(0, limit - int(current))
        return limit


# Global instance
_token_manager = None
_rate_limiter = None

def get_token_manager() -> SecureTokenManager:
    """Get global token manager instance"""
    global _token_manager
    if _token_manager is None:
        _token_manager = SecureTokenManager()
    return _token_manager

def get_token_rate_limiter() -> TokenRateLimiter:
    """Get global token rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = TokenRateLimiter()
    return _rate_limiter