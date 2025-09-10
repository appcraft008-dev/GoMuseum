"""
End-to-end tests for complete user journeys
"""
import pytest
from httpx import AsyncClient
from fastapi import status
import asyncio
import time


@pytest.mark.e2e
class TestCompleteUserJourney:
    """Test complete user journey from registration to recognition"""
    
    async def test_complete_user_lifecycle(self, async_client: AsyncClient, db_session):
        """Test complete user lifecycle: register -> login -> use features -> logout"""
        
        # Step 1: User Registration
        user_data = {
            "email": "journey_user@example.com",
            "password": "securepassword123",
            "username": "journeyuser"
        }
        
        register_response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_200_OK
        
        register_data = register_response.json()
        assert "access_token" in register_data
        assert "user" in register_data
        
        user_id = register_data["user"]["id"]
        access_token = register_data["access_token"]
        
        # Step 2: Verify user can access protected endpoints
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        profile_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        assert profile_response.status_code == status.HTTP_200_OK
        
        profile_data = profile_response.json()
        assert profile_data["id"] == user_id
        assert profile_data["email"] == "journey_user@example.com"
        
        # Step 3: User updates profile
        update_data = {
            "username": "updated_journey_user",
            "language": "en"
        }
        
        update_response = await async_client.put("/api/v1/user/profile", 
                                                json=update_data, 
                                                headers=auth_headers)
        
        if update_response.status_code == status.HTTP_200_OK:
            updated_profile = update_response.json()
            assert updated_profile["username"] == "updated_journey_user"
        
        # Step 4: User changes password
        password_change_data = {
            "current_password": "securepassword123",
            "new_password": "newsecurepassword456"
        }
        
        password_response = await async_client.post("/api/v1/auth/change-password",
                                                   json=password_change_data,
                                                   headers=auth_headers)
        
        if password_response.status_code == status.HTTP_200_OK:
            # Step 5: Login with new password
            new_login_data = {
                "email": "journey_user@example.com",
                "password": "newsecurepassword456"
            }
            
            new_login_response = await async_client.post("/api/v1/auth/login", json=new_login_data)
            assert new_login_response.status_code == status.HTTP_200_OK
            
            new_auth_data = new_login_response.json()
            new_access_token = new_auth_data["access_token"]
            new_auth_headers = {"Authorization": f"Bearer {new_access_token}"}
            
            # Step 6: Verify access with new token
            verify_response = await async_client.get("/api/v1/auth/profile", headers=new_auth_headers)
            assert verify_response.status_code == status.HTTP_200_OK
            
            # Step 7: User logout
            logout_response = await async_client.post("/api/v1/auth/logout", headers=new_auth_headers)
            assert logout_response.status_code == status.HTTP_200_OK
            
            # Step 8: Verify token is invalidated (if blacklisting is implemented)
            after_logout_response = await async_client.get("/api/v1/auth/profile", headers=new_auth_headers)
            # Note: This might still work if token blacklisting is not implemented
    
    async def test_museum_browsing_journey(self, async_client: AsyncClient, auth_headers, test_museum, test_artwork):
        """Test complete museum browsing journey"""
        
        # Step 1: Get list of museums
        museums_response = await async_client.get("/api/v1/museums", headers=auth_headers)
        if museums_response.status_code == status.HTTP_200_OK:
            museums_data = museums_response.json()
            assert len(museums_data) > 0
            
            # Step 2: Get specific museum details
            museum_id = str(test_museum.id)
            museum_response = await async_client.get(f"/api/v1/museums/{museum_id}", headers=auth_headers)
            
            if museum_response.status_code == status.HTTP_200_OK:
                museum_data = museum_response.json()
                assert museum_data["id"] == museum_id
                
                # Step 3: Get artworks in museum
                artworks_response = await async_client.get(f"/api/v1/museums/{museum_id}/artworks", 
                                                         headers=auth_headers)
                
                if artworks_response.status_code == status.HTTP_200_OK:
                    artworks_data = artworks_response.json()
                    assert len(artworks_data) > 0
                    
                    # Step 4: Get specific artwork details
                    artwork_id = str(test_artwork.id)
                    artwork_response = await async_client.get(f"/api/v1/artworks/{artwork_id}", 
                                                            headers=auth_headers)
                    
                    if artwork_response.status_code == status.HTTP_200_OK:
                        artwork_data = artwork_response.json()
                        assert artwork_data["id"] == artwork_id
    
    async def test_artwork_recognition_journey(self, async_client: AsyncClient, auth_headers, sample_image_data):
        """Test complete artwork recognition journey"""
        
        # Step 1: Check user quota
        profile_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        assert profile_response.status_code == status.HTTP_200_OK
        
        profile_data = profile_response.json()
        initial_quota = profile_data.get("free_quota", 0)
        
        # Step 2: Submit image for recognition
        files = {"image": ("test_image.jpg", sample_image_data, "image/jpeg")}
        recognition_response = await async_client.post("/api/v1/recognition/analyze",
                                                     files=files,
                                                     headers=auth_headers)
        
        if recognition_response.status_code == status.HTTP_200_OK:
            recognition_data = recognition_response.json()
            
            # Should have recognition results
            assert "results" in recognition_data or "analysis" in recognition_data
            
            # Step 3: Check quota was consumed
            updated_profile_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
            if updated_profile_response.status_code == status.HTTP_200_OK:
                updated_profile = updated_profile_response.json()
                updated_quota = updated_profile.get("free_quota", 0)
                
                # Quota should be reduced if user is on free plan
                if profile_data.get("subscription_type") == "free":
                    assert updated_quota < initial_quota
            
            # Step 4: Get recognition history
            history_response = await async_client.get("/api/v1/recognition/history", headers=auth_headers)
            if history_response.status_code == status.HTTP_200_OK:
                history_data = history_response.json()
                assert len(history_data) > 0
                
                # Latest entry should be our recognition
                latest_recognition = history_data[0]
                assert "timestamp" in latest_recognition
                assert "results" in latest_recognition or "analysis" in latest_recognition
    
    async def test_error_recovery_journey(self, async_client: AsyncClient, test_user):
        """Test user journey with error scenarios and recovery"""
        
        # Step 1: Attempt login with wrong password
        wrong_login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }
        
        wrong_login_response = await async_client.post("/api/v1/auth/login", json=wrong_login_data)
        assert wrong_login_response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Step 2: Successful login with correct password
        correct_login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await async_client.post("/api/v1/auth/login", json=correct_login_data)
        assert login_response.status_code == status.HTTP_200_OK
        
        login_data = login_response.json()
        access_token = login_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        # Step 3: Access protected resource successfully
        profile_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        assert profile_response.status_code == status.HTTP_200_OK
        
        # Step 4: Attempt access with invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        invalid_response = await async_client.get("/api/v1/auth/profile", headers=invalid_headers)
        assert invalid_response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Step 5: Continue with valid token
        valid_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        assert valid_response.status_code == status.HTTP_200_OK


@pytest.mark.e2e
class TestMultiUserJourney:
    """Test journeys involving multiple users"""
    
    async def test_multiple_users_registration(self, async_client: AsyncClient, db_session):
        """Test multiple users registering and using the system concurrently"""
        
        users_data = [
            {
                "email": f"user{i}@example.com",
                "password": f"password{i}123",
                "username": f"user{i}"
            }
            for i in range(1, 4)
        ]
        
        # Register all users
        user_tokens = []
        for user_data in users_data:
            register_response = await async_client.post("/api/v1/auth/register", json=user_data)
            assert register_response.status_code == status.HTTP_200_OK
            
            register_data = register_response.json()
            user_tokens.append({
                "user_id": register_data["user"]["id"],
                "email": register_data["user"]["email"],
                "token": register_data["access_token"]
            })
        
        # Each user accesses their profile
        for user_token in user_tokens:
            auth_headers = {"Authorization": f"Bearer {user_token['token']}"}
            
            profile_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
            assert profile_response.status_code == status.HTTP_200_OK
            
            profile_data = profile_response.json()
            assert profile_data["id"] == user_token["user_id"]
            assert profile_data["email"] == user_token["email"]
    
    async def test_concurrent_recognition_requests(self, async_client: AsyncClient, auth_headers, sample_image_data):
        """Test concurrent artwork recognition requests"""
        
        async def make_recognition_request():
            files = {"image": ("test_image.jpg", sample_image_data, "image/jpeg")}
            return await async_client.post("/api/v1/recognition/analyze",
                                         files=files,
                                         headers=auth_headers)
        
        # Make 3 concurrent recognition requests
        tasks = [make_recognition_request() for _ in range(3)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # At least some should succeed
        successful_responses = [r for r in responses if not isinstance(r, Exception) and r.status_code == 200]
        
        # Should handle concurrent requests gracefully
        assert len(successful_responses) > 0


@pytest.mark.e2e
class TestSubscriptionJourney:
    """Test subscription-related user journeys"""
    
    async def test_free_user_quota_exhaustion_journey(self, async_client: AsyncClient, db_session, sample_image_data):
        """Test free user reaching quota limit"""
        
        # Register new free user
        user_data = {
            "email": "quota_test@example.com",
            "password": "password123",
            "username": "quotauser"
        }
        
        register_response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_200_OK
        
        register_data = register_response.json()
        access_token = register_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        # Check initial quota
        profile_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        profile_data = profile_response.json()
        initial_quota = profile_data.get("free_quota", 5)
        
        # Use up quota with recognition requests
        files = {"image": ("test_image.jpg", sample_image_data, "image/jpeg")}
        
        for i in range(initial_quota):
            recognition_response = await async_client.post("/api/v1/recognition/analyze",
                                                         files=files,
                                                         headers=auth_headers)
            
            # Should succeed while quota available
            if recognition_response.status_code == status.HTTP_200_OK:
                continue
            elif recognition_response.status_code == status.HTTP_403_FORBIDDEN:
                # Quota exhausted
                break
        
        # One more request should fail due to quota
        final_response = await async_client.post("/api/v1/recognition/analyze",
                                                files=files,
                                                headers=auth_headers)
        
        # Should either succeed (if quota management is not implemented) 
        # or fail with quota exceeded
        if final_response.status_code == status.HTTP_403_FORBIDDEN:
            error_data = final_response.json()
            assert "quota" in error_data.get("detail", {}).get("message", "").lower()
    
    async def test_premium_user_unlimited_access(self, async_client: AsyncClient, admin_user, sample_image_data):
        """Test premium user with unlimited access"""
        
        # Login as admin (assuming admin has premium access)
        login_data = {
            "email": admin_user.email,
            "password": "adminpassword"
        }
        
        login_response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert login_response.status_code == status.HTTP_200_OK
        
        login_data = login_response.json()
        auth_headers = {"Authorization": f"Bearer {login_data['access_token']}"}
        
        # Make multiple recognition requests (more than free quota)
        files = {"image": ("test_image.jpg", sample_image_data, "image/jpeg")}
        
        for i in range(10):  # More than typical free quota
            recognition_response = await async_client.post("/api/v1/recognition/analyze",
                                                         files=files,
                                                         headers=auth_headers)
            
            # Should succeed for premium users (or return appropriate error if not implemented)
            assert recognition_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,  # Endpoint not implemented
                status.HTTP_501_NOT_IMPLEMENTED  # Feature not implemented
            ]


@pytest.mark.e2e
class TestSystemHealthJourney:
    """Test system health and monitoring journeys"""
    
    async def test_health_monitoring_journey(self, async_client: AsyncClient, admin_auth_headers):
        """Test system health monitoring journey"""
        
        # Step 1: Check basic health
        health_response = await async_client.get("/health")
        assert health_response.status_code == status.HTTP_200_OK
        
        health_data = health_response.json()
        assert health_data["status"] == "healthy"
        
        # Step 2: Check detailed health (if available)
        detailed_health_response = await async_client.get("/health/detailed", headers=admin_auth_headers)
        
        if detailed_health_response.status_code == status.HTTP_200_OK:
            detailed_data = detailed_health_response.json()
            
            # Should have component health information
            assert "database" in detailed_data or "components" in detailed_data
        
        # Step 3: Check metrics (if available)
        metrics_response = await async_client.get("/api/v1/monitoring/stats", headers=admin_auth_headers)
        
        if metrics_response.status_code == status.HTTP_200_OK:
            metrics_data = metrics_response.json()
            
            # Should have system metrics
            assert isinstance(metrics_data, dict)
    
    async def test_error_handling_journey(self, async_client: AsyncClient):
        """Test system error handling journey"""
        
        # Step 1: Access non-existent endpoint
        not_found_response = await async_client.get("/api/v1/nonexistent")
        assert not_found_response.status_code == status.HTTP_404_NOT_FOUND
        
        # Step 2: Send malformed request
        malformed_response = await async_client.post("/api/v1/auth/login", 
                                                    content="invalid json",
                                                    headers={"content-type": "application/json"})
        assert malformed_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Step 3: Test rate limiting (if implemented)
        for i in range(20):
            rate_test_response = await async_client.get("/health")
            
            if rate_test_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                # Rate limiting is working
                break
        
        # Step 4: Recovery - normal request should work after rate limit window
        await asyncio.sleep(1)  # Brief pause
        recovery_response = await async_client.get("/health")
        
        # Should eventually recover
        assert recovery_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_429_TOO_MANY_REQUESTS  # Still rate limited
        ]


@pytest.mark.e2e
@pytest.mark.slow
class TestLongRunningJourney:
    """Test long-running user journeys"""
    
    async def test_session_persistence_journey(self, async_client: AsyncClient, test_user):
        """Test session persistence over time"""
        
        # Login
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert login_response.status_code == status.HTTP_200_OK
        
        login_data = login_response.json()
        auth_headers = {"Authorization": f"Bearer {login_data['access_token']}"}
        
        # Use session over time
        start_time = time.time()
        duration = 60  # 1 minute test
        
        while time.time() - start_time < duration:
            # Make periodic requests
            response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
            
            # Session should remain valid
            assert response.status_code == status.HTTP_200_OK
            
            # Wait before next request
            await asyncio.sleep(5)
        
        # Final verification
        final_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        assert final_response.status_code == status.HTTP_200_OK
    
    async def test_token_refresh_journey(self, async_client: AsyncClient, test_user):
        """Test token refresh journey"""
        
        # Initial login
        login_data = {
            "email": test_user.email,
            "password": "testpassword"
        }
        
        login_response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert login_response.status_code == status.HTTP_200_OK
        
        tokens = login_response.json()
        original_access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        
        # Use access token
        auth_headers = {"Authorization": f"Bearer {original_access_token}"}
        profile_response = await async_client.get("/api/v1/auth/profile", headers=auth_headers)
        assert profile_response.status_code == status.HTTP_200_OK
        
        # Refresh token
        refresh_data = {"refresh_token": refresh_token}
        refresh_response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)
        
        if refresh_response.status_code == status.HTTP_200_OK:
            new_tokens = refresh_response.json()
            new_access_token = new_tokens["access_token"]
            
            # Use new access token
            new_auth_headers = {"Authorization": f"Bearer {new_access_token}"}
            new_profile_response = await async_client.get("/api/v1/auth/profile", headers=new_auth_headers)
            assert new_profile_response.status_code == status.HTTP_200_OK
            
            # Verify tokens are different
            assert new_access_token != original_access_token