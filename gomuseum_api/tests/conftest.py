"""
Test configuration and fixtures
"""
import asyncio
import os
import tempfile
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import create_app
from app.core.config import Settings, get_settings
from app.core.database import get_db, Base
from app.core.redis_client import get_redis_client
from app.models.user import User
from app.models.artwork import Artwork
from app.models.museum import Museum


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


class TestSettings(Settings):
    """Test configuration settings"""
    environment: str = "testing"
    database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/15"  # Use different DB for tests
    secret_key: str = "test-secret-key-for-testing-only"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Disable external services for testing
    openai_api_key: str = "test-key"
    anthropic_api_key: str = "test-key"
    
    # Test specific settings
    testing: bool = True
    debug: bool = True


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    """Test settings fixture"""
    return TestSettings()


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine"""
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    return engine


@pytest.fixture(scope="session")
async def async_test_engine():
    """Create async test database engine"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.fixture
async def db_session(async_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    session_factory = sessionmaker(
        bind=async_test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = False
    mock_redis.expire.return_value = True
    mock_redis.flushdb.return_value = True
    return mock_redis


@pytest.fixture
async def test_app(test_settings, db_session, mock_redis):
    """Create test FastAPI application"""
    app = create_app()
    
    # Override dependencies
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis_client] = lambda: mock_redis
    
    yield app
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def test_client(test_app) -> Generator[TestClient, None, None]:
    """Create test client"""
    with TestClient(test_app) as client:
        yield client


@pytest.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client"""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_user(db_session) -> User:
    """Create test user"""
    from app.core.auth import get_password_hash
    
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session) -> User:
    """Create admin test user"""
    from app.core.auth import get_password_hash
    
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword"),
        is_active=True,
        is_verified=True,
        is_superuser=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_museum(db_session) -> Museum:
    """Create test museum"""
    museum = Museum(
        name="Test Museum",
        description="A test museum for testing purposes",
        location="Test City",
        is_active=True
    )
    db_session.add(museum)
    await db_session.commit()
    await db_session.refresh(museum)
    return museum


@pytest.fixture
async def test_artwork(db_session, test_museum) -> Artwork:
    """Create test artwork"""
    artwork = Artwork(
        title="Test Artwork",
        artist="Test Artist",
        description="A test artwork for testing purposes",
        museum_id=test_museum.id,
        year_created=2023,
        style="Test Style",
        medium="Test Medium"
    )
    db_session.add(artwork)
    await db_session.commit()
    await db_session.refresh(artwork)
    return artwork


@pytest.fixture
async def auth_headers(test_user, async_client) -> dict:
    """Create authentication headers for test user"""
    from app.core.auth import create_access_token
    
    access_token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def admin_auth_headers(admin_user, async_client) -> dict:
    """Create authentication headers for admin user"""
    from app.core.auth import create_access_token
    
    access_token = create_access_token(data={"sub": admin_user.username})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content="This is a test artwork response"
                )
            )
        ]
    )
    return mock_client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client"""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[
            MagicMock(
                text="This is a test anthropic response"
            )
        ]
    )
    return mock_client


@pytest.fixture
def sample_image_data():
    """Sample image data for testing"""
    # Create a simple 1x1 pixel image in bytes
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'


@pytest.fixture(autouse=True)
async def cleanup_db(db_session):
    """Clean up database after each test"""
    yield
    # Clean up test data
    await db_session.rollback()


# Performance test fixtures
@pytest.fixture
def performance_thresholds():
    """Performance test thresholds"""
    return {
        "api_response_time": 0.1,  # 100ms
        "cache_response_time": 0.01,  # 10ms
        "db_query_time": 0.05,  # 50ms
        "memory_usage": 100 * 1024 * 1024,  # 100MB
        "cpu_usage": 80.0  # 80%
    }


# Security test fixtures
@pytest.fixture
def security_test_payloads():
    """Security test payloads for injection attacks"""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "1; DELETE FROM users WHERE 1=1; --",
            "1' UNION SELECT NULL, username, password FROM users; --"
        ],
        "xss_payloads": [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "';alert('XSS');//"
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "....//....//....//etc/passwd"
        ]
    }


# Load test data
@pytest.fixture(scope="session")
def load_test_config():
    """Load test configuration"""
    return {
        "concurrent_users": 50,
        "test_duration": 60,  # seconds
        "ramp_up_time": 10,  # seconds
        "endpoints": [
            "/health",
            "/api/v1/auth/login",
            "/api/v1/recognition/analyze",
            "/api/v1/user/profile"
        ]
    }