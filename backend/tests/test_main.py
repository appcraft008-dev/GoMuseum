"""
Comprehensive tests for app.main module
These tests ensure full coverage of the FastAPI application setup
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI


def test_import_app_module():
    """Test that we can import the app module (triggers coverage tracking)"""
    from app import __init__
    assert True


def test_import_models():
    """Test that we can import models module"""
    from app.models import __init__
    assert True


def test_import_schemas():
    """Test that we can import schemas module"""
    from app.schemas import __init__
    assert True


class TestMainApplication:
    """Test suite for main application setup"""

    def test_app_creation(self):
        """Test FastAPI app is created with correct configuration"""
        from app.main import app
        
        assert isinstance(app, FastAPI)
        assert app.title == "GoMuseum API"
        assert app.description == "Backend API service for GoMuseum project - Artwork Recognition"
        assert app.version == "0.1.0"
        assert app.docs_url == "/api/docs"
        assert app.redoc_url == "/api/redoc"
        assert app.openapi_url == "/api/openapi.json"

    def test_cors_middleware_configured(self):
        """Test CORS middleware is properly configured"""
        from app.main import app
        
        # Check that CORS middleware is added (by checking middleware stack)
        middleware_classes = [middleware.cls.__name__ for middleware in app.user_middleware]
        assert 'CORSMiddleware' in middleware_classes

    def test_api_router_included(self):
        """Test that API v1 router is included with correct prefix"""
        from app.main import app
        
        # Check that the API v1 routes are registered
        routes = [str(route.path) for route in app.routes]
        # API routes should be prefixed with /api/v1
        api_routes = [route for route in routes if route.startswith('/api/v1')]
        assert len(api_routes) > 0

    def test_root_endpoint(self):
        """Test root endpoint returns correct response"""
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Welcome to GoMuseum API"
        assert data["docs"] == "/api/docs"
        assert data["version"] == "0.1.0"

    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/api/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_project_info_endpoint(self):
        """Test project info endpoint"""
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/api/info/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["project"] == "GoMuseum"
        assert data["version"] == "0.1.0"
        assert data["description"] == "An AI-powered museum guide platform."
        assert "artwork_recognition" in data["features"]
        assert "ai_powered" in data["features"]
        assert "caching" in data["features"]

    @patch('app.main.init_db')
    def test_startup_event_success(self, mock_init_db):
        """Test successful startup event"""
        from app.main import startup_event
        
        # Mock successful database initialization
        mock_init_db.return_value = None
        
        # Test the startup event
        import asyncio
        asyncio.run(startup_event())
        
        # Verify init_db was called
        mock_init_db.assert_called_once()

    @patch('app.main.init_db')
    @patch('app.main.logger')
    def test_startup_event_database_failure(self, mock_logger, mock_init_db):
        """Test startup event with database initialization failure"""
        from app.main import startup_event
        
        # Mock database initialization failure
        mock_init_db.side_effect = Exception("Database connection failed")
        
        # Test the startup event
        import asyncio
        asyncio.run(startup_event())
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Failed to initialize database" in error_call

    def test_logging_configuration(self):
        """Test that logging is properly configured"""
        from app.main import logger
        
        # Verify logger is created with correct name
        assert logger.name == "app.main"
        
    def test_full_application_startup(self):
        """Integration test for full application startup"""
        with patch('app.main.init_db') as mock_init_db:
            from app.main import app
            
            client = TestClient(app)
            
            # Test that we can make requests to all endpoints
            root_response = client.get("/")
            health_response = client.get("/api/health/")
            info_response = client.get("/api/info/")
            
            assert root_response.status_code == 200
            assert health_response.status_code == 200
            assert info_response.status_code == 200
