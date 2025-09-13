"""
Enhanced Security Configuration Module

Provides secure configuration management with proper key storage,
rotation, and validation mechanisms.
"""

import os
import secrets
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from app.core.logging import get_logger

logger = get_logger(__name__)


class SecureKeyManager:
    """Manages cryptographic keys securely"""
    
    def __init__(self, key_file_path: str = None):
        self.key_file_path = key_file_path or os.environ.get(
            'KEY_FILE_PATH', 
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'keys', 'master.key')
        )
        self.keys_dir = Path(self.key_file_path).parent
        self._ensure_keys_directory()
        self._master_key = self._load_or_generate_master_key()
        self._derived_keys = {}
        
    def _ensure_keys_directory(self):
        """Ensure keys directory exists with proper permissions"""
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (owner read/write only)
        os.chmod(self.keys_dir, 0o700)
        
    def _load_or_generate_master_key(self) -> str:
        """Load existing master key or generate new one"""
        key_file = Path(self.key_file_path)
        
        if key_file.exists():
            # Load existing key
            with open(key_file, 'rb') as f:
                encrypted_key = f.read()
                # In production, decrypt with HSM or KMS
                return encrypted_key.decode('utf-8')
        else:
            # Generate new master key
            master_key = secrets.token_urlsafe(64)
            
            # Store key securely
            with open(key_file, 'wb') as f:
                # In production, encrypt before storing
                f.write(master_key.encode('utf-8'))
            
            # Set restrictive permissions
            os.chmod(key_file, 0o600)
            
            logger.info("Generated new master key")
            return master_key
    
    def get_jwt_secret_key(self) -> str:
        """Get or derive JWT secret key"""
        if 'jwt' not in self._derived_keys:
            # Derive JWT key from master key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'jwt_salt_v1',  # Version the salt for rotation
                iterations=100000,
            )
            key_material = kdf.derive(self._master_key.encode())
            self._derived_keys['jwt'] = base64.urlsafe_b64encode(key_material).decode()
        
        return self._derived_keys['jwt']
    
    def get_encryption_key(self, purpose: str = 'default') -> bytes:
        """Get encryption key for specific purpose"""
        cache_key = f'enc_{purpose}'
        
        if cache_key not in self._derived_keys:
            # Derive purpose-specific encryption key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=f'enc_{purpose}_v1'.encode(),
                iterations=100000,
            )
            key_material = kdf.derive(self._master_key.encode())
            self._derived_keys[cache_key] = base64.urlsafe_b64encode(key_material)
        
        return self._derived_keys[cache_key]
    
    def rotate_keys(self) -> bool:
        """Rotate encryption keys (implement key rotation strategy)"""
        try:
            # Generate new master key
            new_master = secrets.token_urlsafe(64)
            
            # Backup current key
            backup_path = self.key_file_path + f'.backup.{datetime.now().timestamp()}'
            os.rename(self.key_file_path, backup_path)
            
            # Save new key
            with open(self.key_file_path, 'wb') as f:
                f.write(new_master.encode('utf-8'))
            os.chmod(self.key_file_path, 0o600)
            
            # Clear derived keys cache
            self._derived_keys.clear()
            self._master_key = new_master
            
            logger.info("Keys rotated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False


class SecureDataEncryptor:
    """Encrypts sensitive data at rest"""
    
    def __init__(self, key_manager: SecureKeyManager):
        self.key_manager = key_manager
        self._ciphers = {}
    
    def _get_cipher(self, purpose: str = 'default') -> Fernet:
        """Get or create cipher for specific purpose"""
        if purpose not in self._ciphers:
            key = self.key_manager.get_encryption_key(purpose)
            self._ciphers[purpose] = Fernet(key)
        return self._ciphers[purpose]
    
    def encrypt_field(self, data: str, purpose: str = 'default') -> str:
        """Encrypt a field value"""
        if not data:
            return data
        
        cipher = self._get_cipher(purpose)
        encrypted = cipher.encrypt(data.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    
    def decrypt_field(self, encrypted_data: str, purpose: str = 'default') -> str:
        """Decrypt a field value"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            cipher = self._get_cipher(purpose)
            decoded = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted = cipher.decrypt(decoded)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")
    
    def encrypt_dict(self, data: Dict[str, Any], fields: list, purpose: str = 'default') -> Dict[str, Any]:
        """Encrypt specific fields in a dictionary"""
        encrypted_data = data.copy()
        
        for field in fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt_field(str(encrypted_data[field]), purpose)
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any], fields: list, purpose: str = 'default') -> Dict[str, Any]:
        """Decrypt specific fields in a dictionary"""
        decrypted_data = data.copy()
        
        for field in fields:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self.decrypt_field(decrypted_data[field], purpose)
        
        return decrypted_data


class SecurityHeadersConfig:
    """Security headers configuration"""
    
    @staticmethod
    def get_production_headers() -> Dict[str, str]:
        """Get production security headers"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        }
    
    @staticmethod
    def get_development_headers() -> Dict[str, str]:
        """Get development security headers (more permissive for Swagger)"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'"
            )
        }


class InputSanitizer:
    """Input sanitization utilities"""
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """Remove HTML tags and dangerous content"""
        import html
        import re
        
        if not text:
            return text
        
        # HTML entity decode
        text = html.unescape(text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove javascript: and data: URLs
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        text = re.sub(r'data:', '', text, flags=re.IGNORECASE)
        
        # Remove script tags content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Escape special characters
        text = html.escape(text)
        
        return text
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        import re
        
        if not filename:
            return filename
        
        # Remove path components
        filename = os.path.basename(filename)
        
        # Remove dangerous characters
        filename = re.sub(r'[^\w\s\-\.]', '', filename)
        
        # Remove multiple dots
        filename = re.sub(r'\.+', '.', filename)
        
        # Limit length
        max_length = 255
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            filename = name[:max_length-len(ext)] + ext
        
        return filename
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format and domain"""
        import re
        
        if not email:
            return False
        
        # Basic email regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email):
            return False
        
        # Check for malicious patterns
        dangerous_patterns = [
            r'<script', r'javascript:', r'onclick', r'onerror',
            r'\r\n', r'\n', r'\r', r'%0d', r'%0a'
        ]
        
        email_lower = email.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, email_lower):
                return False
        
        # Limit email length
        if len(email) > 254:  # RFC 5321
            return False
        
        return True
    
    @staticmethod
    def validate_image_content(image_bytes: bytes) -> tuple[bool, str]:
        """Validate image content for security threats"""
        import imghdr
        import io
        
        # Check file signatures
        signatures = {
            b'\xff\xd8\xff': 'jpeg',
            b'\x89PNG': 'png', 
            b'GIF8': 'gif',
            b'RIFF': 'webp',
            b'BM': 'bmp'
        }
        
        detected_type = None
        for sig, img_type in signatures.items():
            if image_bytes.startswith(sig):
                detected_type = img_type
                break
        
        if not detected_type:
            return False, "Invalid image format"
        
        # Verify with imghdr
        img_type = imghdr.what(io.BytesIO(image_bytes))
        if not img_type:
            return False, "Cannot determine image type"
        
        # Check for embedded scripts (basic check)
        dangerous_patterns = [
            b'<script', b'javascript:', b'onclick', b'onerror',
            b'<?php', b'<%', b'<jsp:', b'<asp:'
        ]
        
        for pattern in dangerous_patterns:
            if pattern in image_bytes.lower():
                return False, f"Image contains suspicious content"
        
        # Check file size
        max_size = 10 * 1024 * 1024  # 10MB
        if len(image_bytes) > max_size:
            return False, f"Image too large (max {max_size} bytes)"
        
        return True, detected_type


# Initialize global instances
_key_manager = None
_data_encryptor = None

def get_key_manager() -> SecureKeyManager:
    """Get global key manager instance"""
    global _key_manager
    if _key_manager is None:
        _key_manager = SecureKeyManager()
    return _key_manager

def get_data_encryptor() -> SecureDataEncryptor:
    """Get global data encryptor instance"""
    global _data_encryptor
    if _data_encryptor is None:
        _data_encryptor = SecureDataEncryptor(get_key_manager())
    return _data_encryptor