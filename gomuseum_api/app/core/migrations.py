"""
Database migration system for GoMuseum API
Handles database schema creation and updates
"""

import logging
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Any
import asyncio

from .database import engine, Base
from .logging import get_logger

logger = get_logger(__name__)

class DatabaseMigration:
    """Database migration utilities"""
    
    def __init__(self):
        self.migrations = []
    
    async def create_tables(self) -> bool:
        """Create all database tables"""
        try:
            # Create all tables defined in models
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            return False
    
    async def check_tables_exist(self) -> Dict[str, bool]:
        """Check which tables exist in the database"""
        try:
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            # Get all tables defined in models
            model_tables = [table.name for table in Base.metadata.tables.values()]
            
            table_status = {}
            for table in model_tables:
                table_status[table] = table in existing_tables
            
            logger.info(f"Table status: {table_status}")
            return table_status
            
        except Exception as e:
            logger.error(f"Failed to check table existence: {e}")
            return {}
    
    async def add_password_hash_column(self) -> bool:
        """Add password_hash column to users table if it doesn't exist"""
        try:
            with engine.connect() as conn:
                # Check if column exists
                inspector = inspect(engine)
                columns = [col['name'] for col in inspector.get_columns('users')]
                
                if 'password_hash' not in columns:
                    # Add the column
                    conn.execute(text("""
                        ALTER TABLE users 
                        ADD COLUMN password_hash VARCHAR(255)
                    """))
                    conn.commit()
                    logger.info("Added password_hash column to users table")
                else:
                    logger.info("password_hash column already exists")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to add password_hash column: {e}")
            return False
    
    async def create_indexes(self) -> bool:
        """Create database indexes for performance"""
        try:
            with engine.connect() as conn:
                index_queries = [
                    # User table indexes
                    """
                    CREATE INDEX IF NOT EXISTS idx_users_email 
                    ON users(email);
                    """,
                    
                    """
                    CREATE INDEX IF NOT EXISTS idx_users_active 
                    ON users(is_active) WHERE is_active = true;
                    """,
                    
                    # Artwork table indexes
                    """
                    CREATE INDEX IF NOT EXISTS idx_artworks_museum 
                    ON artworks(museum_id);
                    """,
                    
                    """
                    CREATE INDEX IF NOT EXISTS idx_artworks_name 
                    ON artworks(name);
                    """,
                    
                    """
                    CREATE INDEX IF NOT EXISTS idx_artworks_artist 
                    ON artworks(artist);
                    """,
                    
                    # Museum table indexes
                    """
                    CREATE INDEX IF NOT EXISTS idx_museums_active 
                    ON museums(is_active) WHERE is_active = true;
                    """,
                    
                    # Recognition cache indexes
                    """
                    CREATE INDEX IF NOT EXISTS idx_recognition_cache_hash 
                    ON recognition_cache(image_hash);
                    """,
                    
                    """
                    CREATE INDEX IF NOT EXISTS idx_recognition_cache_created 
                    ON recognition_cache(created_at);
                    """
                ]
                
                for query in index_queries:
                    try:
                        conn.execute(text(query))
                        logger.debug(f"Executed index creation: {query[:50]}...")
                    except Exception as e:
                        logger.warning(f"Index creation failed (may already exist): {e}")
                
                conn.commit()
                logger.info("Database indexes created successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            return False
    
    async def seed_test_data(self) -> bool:
        """Seed database with test data for development"""
        try:
            from app.models.user import User
            from app.models.museum import Museum
            from app.models.artwork import Artwork
            from app.core.auth import get_password_hash
            from app.core.database import SessionLocal
            import uuid
            
            db = SessionLocal()
            
            try:
                # Check if data already exists
                existing_users = db.query(User).count()
                if existing_users > 0:
                    logger.info("Test data already exists, skipping seeding")
                    return True
                
                # Create test user
                test_user = User(
                    id=uuid.uuid4(),
                    email="test@gomuseum.com",
                    username="testuser",
                    password_hash=get_password_hash("testpassword123"),
                    is_active=True,
                    subscription_type="premium"
                )
                db.add(test_user)
                
                # Create test museum
                test_museum = Museum(
                    id=uuid.uuid4(),
                    name="Test Museum",
                    name_en="Test Museum",
                    description="A test museum for development",
                    city="Test City",
                    country="Test Country",
                    is_active=True
                )
                db.add(test_museum)
                db.flush()  # Get the museum ID
                
                # Create test artwork
                test_artwork = Artwork(
                    id=uuid.uuid4(),
                    museum_id=test_museum.id,
                    name="Test Artwork",
                    artist="Test Artist",
                    description="A test artwork for development",
                    is_active=True
                )
                db.add(test_artwork)
                
                db.commit()
                logger.info("Test data seeded successfully")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to seed test data: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to seed test data: {e}")
            return False
    
    async def run_migrations(self) -> bool:
        """Run all necessary migrations"""
        try:
            logger.info("Starting database migrations")
            
            # Step 1: Create tables
            if not await self.create_tables():
                return False
            
            # Step 2: Add password_hash column if needed
            if not await self.add_password_hash_column():
                return False
            
            # Step 3: Create indexes
            if not await self.create_indexes():
                return False
            
            # Step 4: Seed test data (only in development)
            from app.core.config import settings
            if settings.environment == "development":
                await self.seed_test_data()
            
            logger.info("Database migrations completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

# Global migration instance
migration = DatabaseMigration()

async def initialize_database():
    """Initialize database with all required tables and data"""
    logger.info("Initializing database")
    success = await migration.run_migrations()
    if success:
        logger.info("✅ Database initialization completed")
    else:
        logger.error("❌ Database initialization failed")
    return success

async def check_database_health() -> Dict[str, Any]:
    """Check database health and status"""
    try:
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Check tables
        table_status = await migration.check_tables_exist()
        
        # Check if we have data
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            from app.models.user import User
            user_count = db.query(User).count()
        finally:
            db.close()
        
        return {
            "connection": "healthy",
            "tables": table_status,
            "user_count": user_count,
            "status": "ready"
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "connection": "failed",
            "error": str(e),
            "status": "unhealthy"
        }