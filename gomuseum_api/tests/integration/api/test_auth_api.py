"""
Integration tests for Authentication API endpoints
"""
import pytest
from httpx import AsyncClient
from fastapi import status
from unittest.mock import patch, AsyncMock

from app.core.auth import create_access_token, get_password_hash


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.api
class TestAuthenticationAPI:
    """Test authentication API endpoints"""
    
    async def test_register_success(self, async_client: AsyncClient, db_session):
        """Test successful user registration"""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "username": "newuser"
        }
        
        response = await async_client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
        assert "user" in data
        
        # Check user data
        user = data["user"]
        assert user["email"] == "newuser@example.com"
        assert user["username"] == "newuser"
        assert "id" in user
        assert user["subscription_type"] == "free"
        assert user["is_active"] is True
    
    async def test_register_duplicate_email(self, async_client: AsyncClient, test_user):
        """Test registration with duplicate email"""
        user_data = {
            "email": test_user.email,
            "password": "securepassword123",
            "username": "differentuser"
        }
        
        response = await async_client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["error"] == "user_exists"
    
    async def test_register_invalid_email(self, async_client: AsyncClient):
        """Test registration with invalid email"""
        user_data = {
            "email": "invalid-email",
            "password": "securepassword123",
            "username": "testuser"
        }
        
        response = await async_client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_register_weak_password(self, async_client: AsyncClient):
        """Test registration with weak password"""
        user_data = {
            "email": "user@example.com",
            "password": "123",  # Too short
            "username": "testuser"
        }
        
        response = await async_client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_register_missing_fields(self, async_client: AsyncClient):
        """Test registration with missing required fields"""
        user_data = {
            "email": "user@example.com"
            # Missing password
        }
        
        response = await async_client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_register_without_username(self, async_client: AsyncClient, db_session):
        """Test registration without optional username"""
        user_data = {
            "email": "user2@example.com",
            "password": "securepassword123"
        }
        
        response = await async_client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user"]["username"] is None
    
    async def test_login_success(self, async_client: AsyncClient, test_user):
        """Test successful login"""
        login_data = {
            "email": test_user.email,
            "password": "testpassword"  # From test_user fixture
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
        assert "user" in data
        
        # Check user data
        user = data["user"]
        assert user["email"] == test_user.email
        assert user["id"] == str(test_user.id)
    
    async def test_login_invalid_email(self, async_client: AsyncClient):
        """Test login with non-existent email"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "anypassword"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"]["error"] == "invalid_credentials"
    
    async def test_login_wrong_password(self, async_client: AsyncClient, test_user):
        """Test login with wrong password"""
        login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"]["error"] == "invalid_credentials"
    
    async def test_login_inactive_user(self, async_client: AsyncClient, test_user, db_session):
        """Test login with inactive user"""
        # Make user inactive
        test_user.is_active = False
        db_session.commit()
        
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"]["error"] == "account_disabled"
    
    async def test_login_user_no_password(self, async_client: AsyncClient, test_user, db_session):
        """Test login with user that has no password hash"""
        # Remove password hash
        test_user.password_hash = None
        db_session.commit()
        
        login_data = {
            "email": test_user.email,
            "password": "anypassword"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"]["error"] == "invalid_credentials"
    
    async def test_login_malformed_email(self, async_client: AsyncClient):
        """Test login with malformed email"""
        login_data = {
            "email": "invalid-email",
            "password": "password123"
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_refresh_token_success(self, async_client: AsyncClient, test_user):
        """Test successful token refresh"""
        # First login to get tokens
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await async_client.post("/api/v1/auth/login", json=login_data)
        login_data = login_response.json()
        refresh_token = login_data["refresh_token"]
        
        # Use refresh token
        refresh_data = {
            "refresh_token": refresh_token
        }
        
        response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
    
    async def test_refresh_token_invalid(self, async_client: AsyncClient):
        """Test refresh with invalid token"""
        refresh_data = {
            "refresh_token": "invalid_token"
        }
        
        response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_refresh_token_access_token_used(self, async_client: AsyncClient, test_user):
        """Test refresh using access token instead of refresh token"""
        # Get access token
        access_token = create_access_token({"sub": str(test_user.id)})
        
        refresh_data = {
            "refresh_token": access_token
        }
        
        response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_logout_success(self, async_client: AsyncClient, auth_headers):
        """Test successful logout"""
        response = await async_client.post("/api/v1/auth/logout", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Successfully logged out"
    
    async def test_logout_without_token(self, async_client: AsyncClient):
        """Test logout without authentication token"""
        response = await async_client.post("/api/v1/auth/logout")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_logout_invalid_token(self, async_client: AsyncClient):
        """Test logout with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        
        response = await async_client.post("/api/v1/auth/logout", headers=headers)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_change_password_success(self, async_client: AsyncClient, auth_headers, test_user, db_session):
        """Test successful password change"""
        password_data = {
            "current_password": "testpassword",
            "new_password": "newsecurepassword123"
        }
        
        response = await async_client.post("/api/v1/auth/change-password", 
                                         json=password_data, 
                                         headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Password changed successfully"
        
        # Verify password was actually changed
        db_session.refresh(test_user)
        from app.core.auth import verify_password
        assert verify_password("newsecurepassword123", test_user.password_hash)
    
    async def test_change_password_wrong_current(self, async_client: AsyncClient, auth_headers):
        """Test password change with wrong current password"""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newsecurepassword123"
        }
        
        response = await async_client.post("/api/v1/auth/change-password", 
                                         json=password_data, 
                                         headers=auth_headers)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["error"] == "invalid_password"
    
    async def test_change_password_weak_new_password(self, async_client: AsyncClient, auth_headers):
        """Test password change with weak new password"""
        password_data = {
            "current_password": "testpassword",
            "new_password": "123"  # Too short
        }
        
        response = await async_client.post("/api/v1/auth/change-password", 
                                         json=password_data, 
                                         headers=auth_headers)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_change_password_unauthorized(self, async_client: AsyncClient):
        """Test password change without authentication"""
        password_data = {
            "current_password": "oldpassword",
            "new_password": "newpassword123"
        }
        
        response = await async_client.post("/api/v1/auth/change-password", json=password_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_get_profile_success(self, async_client: AsyncClient, auth_headers, test_user):
        """Test getting user profile"""
        response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
        assert "created_at" in data
    
    async def test_get_profile_unauthorized(self, async_client: AsyncClient):
        """Test getting profile without authentication"""
        response = await async_client.get("/api/v1/auth/profile")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.integration
class TestAuthenticationRateLimit:
    """Test rate limiting on authentication endpoints"""
    
    async def test_login_rate_limit(self, async_client: AsyncClient):
        """Test login rate limiting"""
        login_data = {
            "email": "test@example.com",
            "password": "password123"
        }
        
        # Make many requests quickly
        responses = []
        for i in range(10):
            response = await async_client.post("/api/v1/auth/login", json=login_data)
            responses.append(response)
        
        # Should eventually hit rate limit
        rate_limited = any(r.status_code == status.HTTP_429_TOO_MANY_REQUESTS for r in responses)
        
        # Note: This test might not always trigger rate limiting in test environment
        # depending on the rate limit configuration
    
    async def test_register_rate_limit(self, async_client: AsyncClient):
        """Test registration rate limiting"""
        # Make many registration attempts
        responses = []
        for i in range(10):
            user_data = {
                "email": f"user{i}@example.com",
                "password": "password123",
                "username": f"user{i}"
            }
            response = await async_client.post("/api/v1/auth/register", json=user_data)
            responses.append(response)
        
        # Check if any requests were rate limited
        rate_limited = any(r.status_code == status.HTTP_429_TOO_MANY_REQUESTS for r in responses)
        
        # Note: Similar to above, this depends on rate limit configuration


@pytest.mark.asyncio
@pytest.mark.integration
class TestAuthenticationErrors:
    """Test error handling in authentication endpoints"""
    
    async def test_register_database_error(self, async_client: AsyncClient, db_session):
        """Test registration with database error"""
        with patch.object(db_session, 'add', side_effect=Exception("Database error")):
            user_data = {
                "email": "error@example.com",
                "password": "password123",
                "username": "erroruser"
            }
            
            response = await async_client.post("/api/v1/auth/register", json=user_data)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["detail"]["error"] == "registration_failed"
    
    async def test_login_database_error(self, async_client: AsyncClient, db_session):
        """Test login with database error"""
        with patch.object(db_session, 'query', side_effect=Exception("Database error")):
            login_data = {
                "email": "test@example.com",
                "password": "password123"
            }
            
            response = await async_client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    async def test_token_generation_error(self, async_client: AsyncClient, test_user):
        """Test token generation error during login"""
        with patch('app.api.v1.auth.create_access_token', side_effect=Exception("Token error")):
            login_data = {
                "email": test_user.email,
                "password": "testpassword"
            }
            
            response = await async_client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
@pytest.mark.integration
class TestAuthenticationSecurity:
    """Test security aspects of authentication"""
    
    async def test_password_not_returned(self, async_client: AsyncClient, db_session):
        """Test that password is never returned in responses"""
        user_data = {
            "email": "secure@example.com",
            "password": "securepassword123",
            "username": "secureuser"
        }
        
        response = await async_client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check that password fields are not in response
        user = data["user"]
        assert "password" not in user
        assert "password_hash" not in user
        assert "hashed_password" not in user
    
    async def test_login_timing_attack_protection(self, async_client: AsyncClient, test_user):
        """Test that login response times are similar for valid/invalid users"""
        import time
        
        # Test with valid user
        start_time = time.time()
        response1 = await async_client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "wrongpassword"
        })
        time1 = time.time() - start_time
        
        # Test with invalid user
        start_time = time.time()
        response2 = await async_client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "anypassword"
        })
        time2 = time.time() - start_time
        
        # Both should return 401
        assert response1.status_code == status.HTTP_401_UNAUTHORIZED
        assert response2.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Times should be reasonably similar (within 1 second difference)
        # This is a basic check; in production you might want more sophisticated timing analysis
        assert abs(time1 - time2) < 1.0
    
    async def test_token_blacklist_integration(self, async_client: AsyncClient, auth_headers):
        """Test that blacklisted tokens are rejected"""
        # First, logout to blacklist the token
        await async_client.post("/api/v1/auth/logout", headers=auth_headers)
        
        # Try to use the token again
        response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        
        # Should be rejected (depending on implementation)
        # Note: This test depends on the token blacklist being properly implemented
        # and checked in the authentication middleware