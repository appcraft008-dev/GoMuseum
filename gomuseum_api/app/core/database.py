from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import asyncio
import logging

from .config import settings

logger = logging.getLogger("app.database")

# Database engine with conditional configuration
def create_database_engine():
    """Create database engine with appropriate configuration for the database type"""
    base_config = {
        "echo": settings.database_echo,
    }
    
    if "sqlite" in settings.database_url:
        # SQLite-specific configuration
        base_config.update({
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        })
    else:
        # PostgreSQL-specific configuration
        base_config.update({
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        })
    
    return create_engine(settings.database_url, **base_config)

engine = create_database_engine()

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()

# Metadata for Alembic
metadata = MetaData()

def get_db():
    """Database dependency for FastAPI endpoints"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    """Initialize database tables (for development only)"""
    # Import all models to register them with Base
    from app.models import user, artwork, museum, recognition_cache
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

async def close_db():
    """Close database connections"""
    engine.dispose()
    logger.info("Database connections closed")

# Connection test
def test_connection():
    """Test database connection"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.fetchone() is not None
    except Exception as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        return False
    
def create_tables():
    """Create all tables (for development)"""
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created successfully")