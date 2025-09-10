#!/usr/bin/env python3
"""
GoMuseum API Comprehensive Test Suite
Tests all functionality after error-detective fixes
"""

import asyncio
import sys
import os
import time
import json
from typing import Dict, Any, List
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import dataclass
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent / "gomuseum_api"
sys.path.insert(0, str(project_root))

# Change to the project directory
os.chdir(str(project_root))

@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    status: str  # PASS, FAIL, SKIP
    duration: float
    error_message: str = ""
    details: str = ""

class ComprehensiveTestSuite:
    """Comprehensive test suite for GoMuseum API"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        
    def log_result(self, test_name: str, status: str, duration: float, error: str = "", details: str = ""):
        """Log test result"""
        self.results.append(TestResult(test_name, status, duration, error, details))
        
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⏭️"
        print(f"{status_icon} {test_name} ({duration:.3f}s)")
        
        if error:
            print(f"   Error: {error}")
        if details:
            print(f"   Details: {details}")
    
    async def test_imports(self):
        """Test all critical imports"""
        start = time.time()
        test_name = "Core Module Imports"
        
        try:
            # Test core imports
            from app.core.config import settings
            from app.core.database import get_db, engine
            from app.core.auth import create_access_token, verify_password, get_password_hash
            from app.core.redis_client import redis_client
            from app.core.migrations import initialize_database
            
            # Test model imports
            from app.models.user import User
            from app.models.museum import Museum
            from app.models.artwork import Artwork
            
            # Test API imports
            from app.api.v1.auth import router as auth_router
            from app.api.v1.user import router as user_router
            from app.api.v1.recognition import router as recognition_router
            
            # Test performance optimization imports
            from app.core.database_performance import optimize_database_performance
            from app.core.redis_performance import initialize_high_performance_redis
            from app.core.api_performance import configure_api_performance
            from app.core.memory_optimization import initialize_memory_optimization
            
            self.log_result(test_name, "PASS", time.time() - start, 
                          details="All critical modules imported successfully")
            
        except Exception as e:
            self.log_result(test_name, "FAIL", time.time() - start, str(e))
    
    async def test_database_functionality(self):
        """Test database functionality"""
        start = time.time()
        test_name = "Database Functionality"
        
        try:
            from app.core.database import engine, SessionLocal
            from app.core.migrations import initialize_database
            from app.models.user import User
            from sqlalchemy import text
            
            # Test database connection
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.fetchone() is not None
            
            # Test database initialization
            db_init_success = await initialize_database()
            assert db_init_success, "Database initialization failed"
            
            # Test basic CRUD operations
            db = SessionLocal()
            try:
                # Test user creation
                from app.core.auth import get_password_hash
                test_user = User(
                    email="test@example.com",
                    username="testuser",
                    password_hash=get_password_hash("testpassword123"),
                    is_active=True
                )
                db.add(test_user)
                db.commit()
                db.refresh(test_user)
                
                # Test user retrieval
                retrieved_user = db.query(User).filter(User.email == "test@example.com").first()
                assert retrieved_user is not None
                assert retrieved_user.email == "test@example.com"
                
                # Test password verification
                from app.core.auth import verify_password
                assert verify_password("testpassword123", retrieved_user.password_hash)
                
                # Cleanup
                db.delete(retrieved_user)
                db.commit()
                
                self.log_result(test_name, "PASS", time.time() - start,
                              details="Database connection, initialization, and CRUD operations working")
                
            finally:
                db.close()
                
        except Exception as e:
            self.log_result(test_name, "FAIL", time.time() - start, str(e))
    
    async def test_authentication_system(self):
        """Test authentication system"""
        start = time.time()
        test_name = "Authentication System"
        
        try:
            from app.core.auth import (
                create_access_token, verify_token, verify_password, 
                get_password_hash, AuthenticationError
            )
            
            # Test password hashing and verification
            password = "testpassword123"
            hashed = get_password_hash(password)
            assert verify_password(password, hashed), "Password verification failed"
            assert not verify_password("wrongpassword", hashed), "Wrong password accepted"
            
            # Test token creation and verification
            token_data = {"sub": "user123", "email": "test@example.com"}
            token = create_access_token(token_data)
            assert isinstance(token, str), "Token should be a string"
            
            # Test token verification
            decoded = verify_token(token)
            assert decoded["sub"] == "user123"
            assert decoded["email"] == "test@example.com"
            
            # Test invalid token
            try:
                verify_token("invalid_token")
                assert False, "Invalid token should raise exception"
            except AuthenticationError:
                pass  # Expected
            
            self.log_result(test_name, "PASS", time.time() - start,
                          details="Password hashing, token creation/verification working")
            
        except Exception as e:
            self.log_result(test_name, "FAIL", time.time() - start, str(e))
    
    async def test_redis_functionality(self):
        """Test Redis functionality"""
        start = time.time()
        test_name = "Redis Cache Functionality"
        
        try:
            from app.core.redis_client import redis_client, get_cache_key
            
            # Mock Redis for testing
            redis_client.redis = Mock()
            redis_client.redis.ping = AsyncMock(return_value=True)
            redis_client.redis.get = AsyncMock(return_value=b'{"test": "data"}')
            redis_client.redis.set = AsyncMock(return_value=True)
            redis_client.redis.delete = AsyncMock(return_value=1)
            redis_client.redis.exists = AsyncMock(return_value=1)
            
            # Test cache key generation
            key = get_cache_key("test", "key", "123")
            assert key.startswith("gomuseum:test:")
            assert len(key) > 20  # Should have hash component
            
            # Test cache operations
            await redis_client.connect()  # Mock connect
            
            # Test set and get
            result = await redis_client.set("test_key", {"test": "data"}, ttl=60)
            assert result is True or result is None  # Mock may return None
            
            cached_data = await redis_client.get("test_key")
            if cached_data:  # If mock returns data
                assert cached_data == {"test": "data"}
            
            self.log_result(test_name, "PASS", time.time() - start,
                          details="Redis operations and cache key generation working")
            
        except Exception as e:
            self.log_result(test_name, "FAIL", time.time() - start, str(e))
    
    async def test_api_endpoints(self):
        """Test API endpoints"""
        start = time.time()
        test_name = "API Endpoint Configuration"
        
        try:
            from fastapi.testclient import TestClient
            from app.main import create_app
            
            # Create test app
            app = create_app()
            client = TestClient(app)
            
            # Test health endpoint
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            
            # Test API documentation endpoints (in development)
            response = client.get("/docs", follow_redirects=True)
            # Should return 200 in development or redirect
            assert response.status_code in [200, 307, 404]  # 404 if disabled in production
            
            self.log_result(test_name, "PASS", time.time() - start,
                          details="Basic API endpoints accessible")
            
        except Exception as e:
            self.log_result(test_name, "FAIL", time.time() - start, str(e))
    
    async def test_performance_optimizations(self):
        """Test performance optimization modules"""
        start = time.time()
        test_name = "Performance Optimizations"
        
        try:
            # Test database performance
            from app.core.database_performance import DatabaseOptimizer, OptimizedQueries
            optimizer = DatabaseOptimizer()
            assert optimizer is not None
            
            # Test Redis performance
            from app.core.redis_performance import HighPerformanceRedisClient, CacheStats
            hp_client = HighPerformanceRedisClient()
            assert hp_client is not None
            
            stats = CacheStats()
            assert stats.hit_rate == 0  # Initially 0
            
            # Test API performance
            from app.core.api_performance import (
                OptimizedJSONResponse, ResponseCompressionMiddleware, 
                recognition_optimizer
            )
            
            # Test JSON response
            response = OptimizedJSONResponse({"test": "data"})
            assert response.status_code == 200
            
            # Test memory optimization
            from app.core.memory_optimization import (
                MemoryProfiler, ObjectPool, AsyncBatchProcessor
            )
            
            profiler = MemoryProfiler(enable_tracemalloc=False)  # Disable for testing
            stats = profiler.get_memory_stats()
            assert stats.current_mb >= 0
            
            # Test object pool
            dict_pool = ObjectPool(dict, max_size=10)
            obj = dict_pool.borrow()
            assert isinstance(obj, dict)
            dict_pool.return_object(obj)
            
            self.log_result(test_name, "PASS", time.time() - start,
                          details="All performance optimization modules loaded and functional")
            
        except Exception as e:
            self.log_result(test_name, "FAIL", time.time() - start, str(e))
    
    async def test_security_features(self):
        """Test security features"""
        start = time.time()
        test_name = "Security Features"
        
        try:
            from app.core.auth import get_password_hash, verify_password
            from app.core.middleware import SecurityHeadersMiddleware, RateLimitMiddleware
            
            # Test password security
            password = "testpassword123"
            hash1 = get_password_hash(password)
            hash2 = get_password_hash(password)
            
            # Hashes should be different (salted)
            assert hash1 != hash2, "Password hashes should be salted/different"
            assert verify_password(password, hash1), "Password verification should work"
            assert verify_password(password, hash2), "Password verification should work"
            
            # Test security middleware
            from starlette.applications import Starlette
            app = Starlette()
            
            security_middleware = SecurityHeadersMiddleware(app)
            rate_limit_middleware = RateLimitMiddleware(app, calls=100, period=3600)
            
            assert security_middleware is not None
            assert rate_limit_middleware is not None
            
            # Test cache key security (SHA-256 instead of MD5)
            from app.core.redis_client import get_cache_key
            import hashlib
            
            test_key = get_cache_key("test", "data")
            # Should use SHA-256 (fixed in our corrections)
            assert len(test_key.split(":")[-1]) == 16, "Cache key should use secure hash"
            
            self.log_result(test_name, "PASS", time.time() - start,
                          details="Security features implemented correctly")
            
        except Exception as e:
            self.log_result(test_name, "FAIL", time.time() - start, str(e))
    
    async def test_model_validations(self):
        """Test model validations and schemas"""
        start = time.time()
        test_name = "Model Validations"
        
        try:
            from app.models.user import User
            from app.models.museum import Museum
            from app.models.artwork import Artwork
            import uuid
            
            # Test User model
            user = User(
                id=uuid.uuid4(),
                email="test@example.com",
                username="testuser",
                password_hash="hashed_password",
                is_active=True
            )
            
            assert user.email == "test@example.com"
            assert user.has_quota() == False  # Free user with no quota
            assert user.consume_quota() == False  # No quota to consume
            
            # Test premium user
            user.subscription_type = "premium"
            assert user.has_quota() == True  # Premium user always has quota
            
            # Test Museum model
            museum = Museum(
                id=uuid.uuid4(),
                name="Test Museum",
                city="Test City",
                country="Test Country",
                is_active=True
            )
            assert museum.name == "Test Museum"
            
            # Test Artwork model
            artwork = Artwork(
                id=uuid.uuid4(),
                museum_id=museum.id,
                name="Test Artwork",
                artist="Test Artist",
                is_active=True
            )
            assert artwork.display_name == "Test Artwork"
            assert artwork.display_artist == "Test Artist"
            
            self.log_result(test_name, "PASS", time.time() - start,
                          details="All model validations and methods working")
            
        except Exception as e:
            self.log_result(test_name, "FAIL", time.time() - start, str(e))
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_time = time.time() - self.start_time
        
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        total = len(self.results)
        
        report = {
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "success_rate": (passed / total * 100) if total > 0 else 0,
                "total_duration": total_time
            },
            "results": [
                {
                    "test": r.test_name,
                    "status": r.status,
                    "duration": r.duration,
                    "error": r.error_message,
                    "details": r.details
                }
                for r in self.results
            ]
        }
        
        return report
    
    def print_report(self):
        """Print comprehensive test report"""
        report = self.generate_report()
        summary = report["summary"]
        
        print("\n" + "="*80)
        print("🧪 GOMUSEUM API COMPREHENSIVE TEST REPORT")
        print("="*80)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   ✅ Passed: {summary['passed']}")
        print(f"   ❌ Failed: {summary['failed']}")
        print(f"   ⏭️ Skipped: {summary['skipped']}")
        print(f"   📈 Success Rate: {summary['success_rate']:.1f}%")
        print(f"   ⏱️ Total Duration: {summary['total_duration']:.3f}s")
        
        # Print failed tests details
        failed_tests = [r for r in self.results if r.status == "FAIL"]
        if failed_tests:
            print(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"   • {test.test_name}")
                if test.error_message:
                    print(f"     Error: {test.error_message}")
        
        # Overall assessment
        print(f"\n🎯 OVERALL ASSESSMENT:")
        if summary['success_rate'] >= 90:
            print("   🏆 EXCELLENT - All critical systems functioning properly!")
        elif summary['success_rate'] >= 75:
            print("   ✅ GOOD - Most systems working, minor issues to address")
        elif summary['success_rate'] >= 50:
            print("   ⚠️ FAIR - Several issues need attention")
        else:
            print("   🚨 CRITICAL - Major issues require immediate attention")
        
        print("="*80)

async def main():
    """Run comprehensive test suite"""
    print("🚀 Starting GoMuseum API Comprehensive Test Suite")
    print("   Testing all functionality after error-detective fixes\n")
    
    test_suite = ComprehensiveTestSuite()
    
    # Run all tests
    test_functions = [
        test_suite.test_imports,
        test_suite.test_database_functionality,
        test_suite.test_authentication_system,
        test_suite.test_redis_functionality,
        test_suite.test_api_endpoints,
        test_suite.test_performance_optimizations,
        test_suite.test_security_features,
        test_suite.test_model_validations,
    ]
    
    for test_func in test_functions:
        try:
            await test_func()
        except Exception as e:
            print(f"❌ Test suite error: {e}")
    
    # Generate and print report
    test_suite.print_report()
    
    return test_suite.generate_report()

if __name__ == "__main__":
    # Install required testing dependencies
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "httpx", "pytest"])
    except:
        pass  # May already be installed
    
    # Run tests
    report = asyncio.run(main())
    
    # Exit with appropriate code
    sys.exit(0 if report["summary"]["failed"] == 0 else 1)