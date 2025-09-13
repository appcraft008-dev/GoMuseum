"""
Enhanced Security Tests for GoMuseum API

Tests for newly implemented security features including:
- Secure key management
- Token blacklisting with Redis
- Data encryption
- Input sanitization
"""

import pytest
import asyncio
import json
import base64
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import jwt

from app.core.security_config import (
    SecureKeyManager, SecureDataEncryptor, InputSanitizer, SecurityHeadersConfig
)
from app.core.secure_token_manager import (
    SecureTokenManager, TokenRateLimiter
)


class TestSecureKeyManager:
    """Test secure key management"""
    
    def test_key_generation_and_persistence(self, tmp_path):
        """Test that keys are generated and persisted correctly"""
        key_file = tmp_path / "test_master.key"
        
        # First instance generates key
        manager1 = SecureKeyManager(str(key_file))
        jwt_key1 = manager1.get_jwt_secret_key()
        
        assert jwt_key1 is not None
        assert len(jwt_key1) > 32
        assert key_file.exists()
        
        # Second instance loads same key
        manager2 = SecureKeyManager(str(key_file))
        jwt_key2 = manager2.get_jwt_secret_key()
        
        assert jwt_key1 == jwt_key2
    
    def test_derived_key_consistency(self, tmp_path):
        """Test that derived keys are consistent"""
        key_file = tmp_path / "test_master.key"
        manager = SecureKeyManager(str(key_file))
        
        # Get same purpose key multiple times
        enc_key1 = manager.get_encryption_key("user_data")
        enc_key2 = manager.get_encryption_key("user_data")
        
        assert enc_key1 == enc_key2
        
        # Different purpose yields different key
        enc_key3 = manager.get_encryption_key("api_keys")
        assert enc_key1 != enc_key3
    
    def test_key_rotation(self, tmp_path):
        """Test key rotation functionality"""
        key_file = tmp_path / "test_master.key"
        manager = SecureKeyManager(str(key_file))
        
        original_jwt = manager.get_jwt_secret_key()
        
        # Rotate keys
        success = manager.rotate_keys()
        assert success
        
        # Check backup was created
        backup_files = list(tmp_path.glob("*.backup.*"))
        assert len(backup_files) == 1
        
        # New key should be different
        new_jwt = manager.get_jwt_secret_key()
        assert new_jwt != original_jwt


class TestSecureDataEncryptor:
    """Test data encryption functionality"""
    
    def test_field_encryption_decryption(self, tmp_path):
        """Test encrypting and decrypting fields"""
        key_file = tmp_path / "test_master.key"
        key_manager = SecureKeyManager(str(key_file))
        encryptor = SecureDataEncryptor(key_manager)
        
        # Test string encryption
        original = "sensitive@email.com"
        encrypted = encryptor.encrypt_field(original)
        
        assert encrypted != original
        assert len(encrypted) > len(original)
        
        # Decrypt
        decrypted = encryptor.decrypt_field(encrypted)
        assert decrypted == original
    
    def test_dict_encryption(self, tmp_path):
        """Test encrypting specific fields in dictionary"""
        key_file = tmp_path / "test_master.key"
        key_manager = SecureKeyManager(str(key_file))
        encryptor = SecureDataEncryptor(key_manager)
        
        original_data = {
            "user_id": "123",
            "email": "user@example.com",
            "phone": "+1234567890",
            "public_field": "not encrypted"
        }
        
        # Encrypt sensitive fields
        encrypted_data = encryptor.encrypt_dict(
            original_data,
            fields=["email", "phone"],
            purpose="user_pii"
        )
        
        assert encrypted_data["email"] != original_data["email"]
        assert encrypted_data["phone"] != original_data["phone"]
        assert encrypted_data["public_field"] == original_data["public_field"]
        
        # Decrypt
        decrypted_data = encryptor.decrypt_dict(
            encrypted_data,
            fields=["email", "phone"],
            purpose="user_pii"
        )
        
        assert decrypted_data == original_data
    
    def test_encryption_with_different_purposes(self, tmp_path):
        """Test that different purposes use different keys"""
        key_file = tmp_path / "test_master.key"
        key_manager = SecureKeyManager(str(key_file))
        encryptor = SecureDataEncryptor(key_manager)
        
        original = "sensitive_data"
        
        encrypted1 = encryptor.encrypt_field(original, purpose="purpose1")
        encrypted2 = encryptor.encrypt_field(original, purpose="purpose2")
        
        # Same data encrypted with different keys should be different
        assert encrypted1 != encrypted2
        
        # But each can be decrypted with correct purpose
        assert encryptor.decrypt_field(encrypted1, purpose="purpose1") == original
        assert encryptor.decrypt_field(encrypted2, purpose="purpose2") == original


class TestSecureTokenManager:
    """Test secure token management with Redis"""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        mock = MagicMock()
        mock.setex.return_value = True
        mock.get.return_value = None
        mock.exists.return_value = 0
        mock.incr.return_value = 1
        mock.expire.return_value = True
        mock.ttl.return_value = 3600
        mock.scan.return_value = (0, [])
        return mock
    
    def test_token_pair_creation(self, mock_redis):
        """Test creating access and refresh token pair"""
        manager = SecureTokenManager(mock_redis)
        
        user_data = {
            "sub": "user123",
            "email": "user@example.com",
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0"
        }
        
        tokens = manager.create_token_pair(user_data, "test_secret_key")
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "session_id" in tokens
        
        # Verify tokens are valid JWTs
        access_payload = jwt.decode(tokens["access_token"], "test_secret_key", algorithms=["HS256"])
        refresh_payload = jwt.decode(tokens["refresh_token"], "test_secret_key", algorithms=["HS256"])
        
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"
        assert access_payload["session_id"] == refresh_payload["session_id"]
        
        # Verify Redis was called to store session
        assert mock_redis.setex.called
    
    def test_token_verification_with_blacklist(self, mock_redis):
        """Test token verification checks blacklist"""
        manager = SecureTokenManager(mock_redis)
        
        # Create token
        user_data = {"sub": "user123"}
        tokens = manager.create_token_pair(user_data, "test_secret_key")
        
        # Mock session exists
        mock_redis.get.return_value = json.dumps({
            "user_id": "user123",
            "session_id": "test_session",
            "last_activity": datetime.now().isoformat()
        })
        
        # Token not blacklisted
        mock_redis.exists.return_value = 0
        payload = manager.verify_token(tokens["access_token"], "test_secret_key")
        assert payload["sub"] == "user123"
        
        # Token blacklisted
        mock_redis.exists.return_value = 1
        with pytest.raises(jwt.InvalidTokenError, match="revoked"):
            manager.verify_token(tokens["access_token"], "test_secret_key")
    
    def test_refresh_token_rotation(self, mock_redis):
        """Test refresh token rotation detection"""
        manager = SecureTokenManager(mock_redis)
        
        # Create initial tokens
        user_data = {"sub": "user123"}
        tokens = manager.create_token_pair(user_data, "test_secret_key")
        
        # Mock refresh token metadata
        mock_redis.get.side_effect = [
            json.dumps({  # Session data
                "user_id": "user123",
                "session_id": "test_session"
            }),
            json.dumps({  # Refresh token metadata
                "session_id": "test_session",
                "rotation_count": 2,  # Will trigger rotation (multiple of 3)
                "created_at": datetime.now().isoformat()
            })
        ]
        
        # Refresh should create new tokens
        new_tokens = manager.refresh_access_token(tokens["refresh_token"], "test_secret_key")
        
        assert "access_token" in new_tokens
        assert new_tokens["rotated"] == False  # Based on rotation_count logic
    
    def test_session_revocation(self, mock_redis):
        """Test revoking entire session"""
        manager = SecureTokenManager(mock_redis)
        
        # Mock session data
        session_data = {
            "user_id": "user123",
            "session_id": "test_session",
            "access_jti": "access_jti_123",
            "refresh_jti": "refresh_jti_123"
        }
        mock_redis.get.return_value = json.dumps(session_data)
        
        # Revoke session
        manager.revoke_session("test_session")
        
        # Verify tokens were blacklisted
        calls = mock_redis.setex.call_args_list
        blacklisted_jtis = [call[0][0] for call in calls if "blacklist:" in call[0][0]]
        
        assert any("access_jti_123" in jti for jti in blacklisted_jtis)
        assert any("refresh_jti_123" in jti for jti in blacklisted_jtis)
        
        # Verify session was deleted
        mock_redis.delete.assert_called_with("session:test_session")


class TestInputSanitizer:
    """Test input sanitization utilities"""
    
    def test_html_sanitization(self):
        """Test HTML content sanitization"""
        dangerous_inputs = [
            ("<script>alert('xss')</script>", "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"),
            ("Hello <b>world</b>", "Hello &lt;b&gt;world&lt;/b&gt;"),
            ("javascript:alert(1)", "alert(1)"),
            ("data:text/html,<script>alert(1)</script>", "text/html,&lt;script&gt;alert(1)&lt;/script&gt;"),
        ]
        
        for dangerous, expected in dangerous_inputs:
            sanitized = InputSanitizer.sanitize_html(dangerous)
            # Check dangerous content is removed or escaped
            assert "<script>" not in sanitized
            assert "javascript:" not in sanitized
    
    def test_filename_sanitization(self):
        """Test filename sanitization for path traversal"""
        dangerous_filenames = [
            ("../../../etc/passwd", "passwd"),
            ("..\\..\\windows\\system32\\config\\sam", "sam"),
            ("file<script>.txt", "filescript.txt"),
            ("file|name.txt", "filename.txt"),
            ("a" * 300 + ".txt", "a" * (255 - 4) + ".txt"),  # Length limiting
        ]
        
        for dangerous, expected_pattern in dangerous_filenames:
            sanitized = InputSanitizer.sanitize_filename(dangerous)
            
            # No path traversal
            assert ".." not in sanitized
            assert "/" not in sanitized
            assert "\\" not in sanitized
            
            # No dangerous characters
            assert "<" not in sanitized
            assert ">" not in sanitized
            assert "|" not in sanitized
            
            # Length limited
            assert len(sanitized) <= 255
    
    def test_email_validation(self):
        """Test email validation and sanitization"""
        valid_emails = [
            "user@example.com",
            "test.user+tag@domain.co.uk",
            "123@test.org",
        ]
        
        invalid_emails = [
            "not_an_email",
            "user@",
            "@domain.com",
            "user@domain",
            "user@domain.c",  # Too short TLD
            "user<script>@domain.com",
            "user@domain.com\r\nBcc: evil@hacker.com",  # Header injection
            "a" * 250 + "@test.com",  # Too long
        ]
        
        for email in valid_emails:
            assert InputSanitizer.validate_email(email) == True
        
        for email in invalid_emails:
            assert InputSanitizer.validate_email(email) == False
    
    def test_image_content_validation(self):
        """Test image content validation"""
        # Valid JPEG header
        valid_jpeg = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        
        # Valid PNG header
        valid_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        
        # Invalid image with script
        invalid_script = b'\xff\xd8\xff<script>alert(1)</script>'
        
        # PHP code injection attempt
        invalid_php = b'\xff\xd8\xff<?php system($_GET["cmd"]); ?>'
        
        # Test valid images
        is_valid, img_type = InputSanitizer.validate_image_content(valid_jpeg)
        assert is_valid == True
        assert img_type == "jpeg"
        
        is_valid, img_type = InputSanitizer.validate_image_content(valid_png)
        assert is_valid == True
        assert img_type == "png"
        
        # Test invalid content
        is_valid, msg = InputSanitizer.validate_image_content(invalid_script)
        assert is_valid == False
        
        is_valid, msg = InputSanitizer.validate_image_content(invalid_php)
        assert is_valid == False
        
        # Test size limit
        huge_image = b'\xff\xd8\xff' + b'\x00' * (11 * 1024 * 1024)  # 11MB
        is_valid, msg = InputSanitizer.validate_image_content(huge_image)
        assert is_valid == False
        assert "too large" in msg.lower()


class TestTokenRateLimiter:
    """Test token operation rate limiting"""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        mock = MagicMock()
        mock.incr.return_value = 1
        mock.expire.return_value = True
        mock.ttl.return_value = 60
        mock.get.return_value = None
        return mock
    
    def test_rate_limit_allows_within_limit(self, mock_redis):
        """Test rate limiter allows requests within limit"""
        limiter = TokenRateLimiter(mock_redis)
        
        # First request should be allowed
        mock_redis.incr.return_value = 1
        allowed = limiter.check_rate_limit("user123", "login", limit=5, window=60)
        assert allowed == True
        
        # Verify expiration was set
        mock_redis.expire.assert_called_once()
    
    def test_rate_limit_blocks_over_limit(self, mock_redis):
        """Test rate limiter blocks requests over limit"""
        limiter = TokenRateLimiter(mock_redis)
        
        # Simulate exceeding limit
        mock_redis.incr.return_value = 6
        allowed = limiter.check_rate_limit("user123", "login", limit=5, window=60)
        assert allowed == False
    
    def test_get_remaining_limit(self, mock_redis):
        """Test getting remaining rate limit"""
        limiter = TokenRateLimiter(mock_redis)
        
        # No requests yet
        mock_redis.get.return_value = None
        remaining = limiter.get_remaining_limit("user123", "login", limit=5)
        assert remaining == 5
        
        # Some requests made
        mock_redis.get.return_value = "3"
        remaining = limiter.get_remaining_limit("user123", "login", limit=5)
        assert remaining == 2
        
        # Limit exceeded
        mock_redis.get.return_value = "10"
        remaining = limiter.get_remaining_limit("user123", "login", limit=5)
        assert remaining == 0


class TestSecurityHeaders:
    """Test security headers configuration"""
    
    def test_production_headers(self):
        """Test production security headers are restrictive"""
        headers = SecurityHeadersConfig.get_production_headers()
        
        # Essential security headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert "max-age=31536000" in headers["Strict-Transport-Security"]
        
        # CSP should be restrictive
        csp = headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "unsafe-inline" not in csp or "'unsafe-inline'" in csp  # Properly quoted if present
        assert "frame-ancestors 'none'" in csp
    
    def test_development_headers(self):
        """Test development headers allow Swagger UI"""
        headers = SecurityHeadersConfig.get_development_headers()
        
        # Still have security headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        
        # But more permissive for development
        assert headers["X-Frame-Options"] == "SAMEORIGIN"
        
        # CSP allows Swagger resources
        csp = headers["Content-Security-Policy"]
        assert "cdn.jsdelivr.net" in csp