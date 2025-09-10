"""
Unit tests for authentication module
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, status
import jwt

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_password,
    get_password_hash,
    get_current_user,
    require_auth,
    AuthenticationError,
    AuthorizationError,
    TokenBlacklist,
    UserRateLimit
)
from app.core.config import settings


class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_password_hash_and_verify(self):
        """Test password hashing and verification"""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        # Hash should be different from original password
        assert hashed != password
        assert len(hashed) > 0
        
        # Verification should work
        assert verify_password(password, hashed) is True
        
        # Wrong password should fail
        assert verify_password("wrong_password", hashed) is False
    
    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes"""
        password1 = "password1"
        password2 = "password2"
        
        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)
        
        assert hash1 != hash2
    
    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes (salt)"""
        password = "same_password"
        
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Should be different due to salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTTokens:
    """Test JWT token creation and verification"""
    
    def test_create_access_token_basic(self):
        """Test basic access token creation"""
        data = {"sub": "test_user"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode and verify structure
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        assert payload["sub"] == "test_user"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_create_access_token_with_expiry(self):
        """Test access token creation with custom expiry"""
        data = {"sub": "test_user"}
        expires_delta = timedelta(minutes=15)
        token = create_access_token(data, expires_delta)
        
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        exp_time = datetime.fromtimestamp(payload["exp"], timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], timezone.utc)
        
        # Should expire in approximately 15 minutes
        time_diff = exp_time - iat_time
        assert abs(time_diff.total_seconds() - 900) < 5  # 15 minutes ± 5 seconds
    
    def test_create_refresh_token(self):
        """Test refresh token creation"""
        user_id = "test_user_123"
        token = create_refresh_token(user_id)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_verify_token_valid(self):
        """Test verification of valid token"""
        data = {"sub": "test_user", "role": "user"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        assert payload["sub"] == "test_user"
        assert payload["type"] == "access"
    
    def test_verify_token_expired(self):
        """Test verification of expired token"""
        data = {"sub": "test_user"}
        # Create token that expires immediately
        expires_delta = timedelta(seconds=-1)
        token = create_access_token(data, expires_delta)
        
        with pytest.raises(AuthenticationError, match="Token expired"):
            verify_token(token)
    
    def test_verify_token_invalid_signature(self):
        """Test verification of token with invalid signature"""
        # Create token with wrong secret
        data = {"sub": "test_user", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        token = jwt.encode(data, "wrong_secret", algorithm="HS256")
        
        with pytest.raises(AuthenticationError, match="Token validation failed"):
            verify_token(token)
    
    def test_verify_token_invalid_type(self):
        """Test verification of token with invalid type"""
        data = {
            "sub": "test_user",
            "type": "invalid_type",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc)
        }
        token = jwt.encode(data, settings.secret_key, algorithm="HS256")
        
        with pytest.raises(AuthenticationError, match="Invalid token type"):
            verify_token(token)


class TestTokenBlacklist:
    """Test token blacklist functionality"""
    
    def setUp(self):
        # Clear blacklist before each test
        TokenBlacklist._blacklisted_tokens.clear()
    
    def test_add_and_check_blacklisted_token(self):
        """Test adding and checking blacklisted tokens"""
        token = "test_token_123"
        
        # Initially not blacklisted
        assert TokenBlacklist.is_blacklisted(token) is False
        
        # Add to blacklist
        TokenBlacklist.add_token(token)
        
        # Now should be blacklisted
        assert TokenBlacklist.is_blacklisted(token) is True
    
    def test_different_tokens_independent(self):
        """Test that different tokens are independent"""
        token1 = "token_1"
        token2 = "token_2"
        
        TokenBlacklist.add_token(token1)
        
        assert TokenBlacklist.is_blacklisted(token1) is True
        assert TokenBlacklist.is_blacklisted(token2) is False


class TestUserRateLimit:
    """Test user rate limiting functionality"""
    
    def setUp(self):
        # Clear rate limit data before each test
        UserRateLimit._user_requests.clear()
    
    def test_rate_limit_within_limit(self):
        """Test requests within rate limit"""
        user_id = "test_user"
        limit = 5
        window = 60  # 1 minute
        
        # Should allow requests within limit
        for i in range(limit):
            assert UserRateLimit.check_rate_limit(user_id, limit, window) is True
    
    def test_rate_limit_exceeded(self):
        """Test rate limit exceeded"""
        user_id = "test_user"
        limit = 3
        window = 60
        
        # Fill up the limit
        for i in range(limit):
            assert UserRateLimit.check_rate_limit(user_id, limit, window) is True
        
        # Next request should be blocked
        assert UserRateLimit.check_rate_limit(user_id, limit, window) is False
    
    def test_rate_limit_different_users(self):
        """Test rate limiting for different users"""
        user1 = "user_1"
        user2 = "user_2"
        limit = 2
        window = 60
        
        # Fill limit for user1
        for i in range(limit):
            assert UserRateLimit.check_rate_limit(user1, limit, window) is True
        
        # user1 should be blocked
        assert UserRateLimit.check_rate_limit(user1, limit, window) is False
        
        # user2 should still be allowed
        assert UserRateLimit.check_rate_limit(user2, limit, window) is True


@pytest.mark.asyncio
class TestAuthenticationDependencies:
    """Test FastAPI authentication dependencies"""
    
    async def test_get_current_user_no_credentials(self, db_session):
        """Test get_current_user with no credentials"""
        result = await get_current_user(credentials=None, db=db_session)
        assert result is None
    
    async def test_get_current_user_valid_token(self, db_session, test_user):
        """Test get_current_user with valid token"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        # Create token for test user
        token = create_access_token({"sub": str(test_user.id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        
        # Mock database query
        with patch('app.models.user.User') as mock_user_model:
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = test_user
            db_session.query = Mock(return_value=mock_query)
            
            result = await get_current_user(credentials=credentials, db=db_session)
            
            assert result is not None
            assert result["id"] == str(test_user.id)
            assert result["email"] == test_user.email
            assert result["username"] == test_user.username
    
    async def test_get_current_user_invalid_token(self, db_session):
        """Test get_current_user with invalid token"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", 
            credentials="invalid_token"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, db=db_session)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_get_current_user_user_not_found(self, db_session):
        """Test get_current_user when user not found in database"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        token = create_access_token({"sub": "nonexistent_user"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        
        # Mock database query to return None
        with patch('app.models.user.User') as mock_user_model:
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = None
            db_session.query = Mock(return_value=mock_query)
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=credentials, db=db_session)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_get_current_user_inactive_user(self, db_session, test_user):
        """Test get_current_user with inactive user"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        # Make user inactive
        test_user.is_active = False
        
        token = create_access_token({"sub": str(test_user.id)})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        
        with patch('app.models.user.User') as mock_user_model:
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = test_user
            db_session.query = Mock(return_value=mock_query)
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=credentials, db=db_session)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_require_auth_with_user(self):
        """Test require_auth with authenticated user"""
        current_user = {"id": "123", "username": "testuser"}
        
        result = await require_auth(current_user)
        assert result == current_user
    
    async def test_require_auth_without_user(self):
        """Test require_auth without authenticated user"""
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(None)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestSubscriptionRequirements:
    """Test subscription-based access control"""
    
    def test_require_premium_with_premium_user(self):
        """Test premium requirement with premium user"""
        from app.core.auth import require_premium
        
        current_user = {
            "id": "123",
            "username": "premiumuser",
            "subscription_type": "premium"
        }
        
        # Should not raise exception
        result = require_premium.dependency(current_user)
        assert result == current_user
    
    def test_require_premium_with_enterprise_user(self):
        """Test premium requirement with enterprise user"""
        from app.core.auth import require_premium
        
        current_user = {
            "id": "123",
            "username": "enterpriseuser",
            "subscription_type": "enterprise"
        }
        
        # Should not raise exception
        result = require_premium.dependency(current_user)
        assert result == current_user
    
    def test_require_premium_with_free_user(self):
        """Test premium requirement with free user"""
        from app.core.auth import require_premium
        
        current_user = {
            "id": "123",
            "username": "freeuser",
            "subscription_type": "free"
        }
        
        with pytest.raises(HTTPException) as exc_info:
            require_premium.dependency(current_user)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient_subscription" in str(exc_info.value.detail)
    
    def test_require_enterprise_with_enterprise_user(self):
        """Test enterprise requirement with enterprise user"""
        from app.core.auth import require_enterprise
        
        current_user = {
            "id": "123",
            "username": "enterpriseuser",
            "subscription_type": "enterprise"
        }
        
        # Should not raise exception
        result = require_enterprise.dependency(current_user)
        assert result == current_user
    
    def test_require_enterprise_with_premium_user(self):
        """Test enterprise requirement with premium user"""
        from app.core.auth import require_enterprise
        
        current_user = {
            "id": "123",
            "username": "premiumuser",
            "subscription_type": "premium"
        }
        
        with pytest.raises(HTTPException) as exc_info:
            require_enterprise.dependency(current_user)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.unit
@pytest.mark.auth
class TestAuthenticationEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_create_token_with_empty_data(self):
        """Test token creation with empty data"""
        token = create_access_token({})
        
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_verify_token_malformed(self):
        """Test verification of malformed token"""
        malformed_token = "not.a.jwt.token"
        
        with pytest.raises(AuthenticationError):
            verify_token(malformed_token)
    
    def test_password_hash_empty_string(self):
        """Test password hashing with empty string"""
        hashed = get_password_hash("")
        assert len(hashed) > 0
        assert verify_password("", hashed) is True
    
    def test_rate_limit_edge_case_window_boundary(self):
        """Test rate limiting at window boundary"""
        user_id = "test_user"
        limit = 1
        window = 1  # 1 second
        
        # First request should pass
        assert UserRateLimit.check_rate_limit(user_id, limit, window) is True
        
        # Second request should fail
        assert UserRateLimit.check_rate_limit(user_id, limit, window) is False
        
        # Wait for window to pass and try again
        import time
        time.sleep(1.1)
        
        # Should be allowed again
        assert UserRateLimit.check_rate_limit(user_id, limit, window) is True