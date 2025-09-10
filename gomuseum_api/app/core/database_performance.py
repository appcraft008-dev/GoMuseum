"""
Database performance optimization module
Optimizes database queries, indexes, and connection pooling for maximum performance
"""

from sqlalchemy import text, Index, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Dict, Any, Optional
import asyncpg
import asyncio
from contextlib import asynccontextmanager
import time
import logging

from .database import engine, SessionLocal
from .redis_client import redis_client, get_cache_key
from .logging import get_logger

logger = get_logger(__name__)

class DatabaseOptimizer:
    """Database performance optimization utilities"""
    
    def __init__(self):
        self.query_cache = {}
        self.prepared_statements = {}
        
    async def optimize_indexes(self):
        """Create optimized indexes for high-performance queries"""
        optimization_queries = [
            # User table optimizations
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_active 
            ON users(email) WHERE is_active = true;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_subscription_quota 
            ON users(subscription_type, free_quota) WHERE is_active = true;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_last_seen 
            ON users(last_seen) WHERE last_seen IS NOT NULL;
            """,
            
            # Artwork table optimizations
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artworks_museum_active 
            ON artworks(museum_id) WHERE is_active = true;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artworks_popularity_featured 
            ON artworks(popularity_score DESC, is_featured DESC) WHERE is_active = true;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artworks_recognition_count 
            ON artworks(recognition_count DESC) WHERE is_active = true;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artworks_search_vector 
            ON artworks USING gin(to_tsvector('english', coalesce(name, '') || ' ' || coalesce(artist, '')));
            """,
            
            # Museum table optimizations
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_museums_location_active 
            ON museums(city, country) WHERE is_active = true;
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_museums_rating 
            ON museums(rating DESC) WHERE is_active = true;
            """,
            
            # Recognition cache optimizations
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_recognition_cache_created 
            ON recognition_cache(created_at DESC);
            """,
            
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_recognition_cache_confidence 
            ON recognition_cache(confidence DESC) WHERE confidence > 0.8;
            """
        ]
        
        try:
            with engine.connect() as conn:
                for query in optimization_queries:
                    try:
                        await asyncio.to_thread(conn.execute, text(query))
                        logger.info(f"Executed optimization query: {query[:50]}...")
                    except Exception as e:
                        logger.warning(f"Index creation failed (may already exist): {e}")
                        
            logger.info("Database index optimization completed")
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
    
    async def create_materialized_views(self):
        """Create materialized views for complex queries"""
        views = [
            # Popular artworks view
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_popular_artworks AS
            SELECT 
                a.id,
                a.name,
                a.artist,
                a.museum_id,
                a.recognition_count,
                a.popularity_score,
                m.name as museum_name,
                m.city,
                m.country
            FROM artworks a
            JOIN museums m ON a.museum_id = m.id
            WHERE a.is_active = true AND m.is_active = true
            ORDER BY a.popularity_score DESC, a.recognition_count DESC
            LIMIT 1000;
            """,
            
            # Museum statistics view
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_museum_stats AS
            SELECT 
                m.id,
                m.name,
                m.city,
                m.country,
                COUNT(a.id) as artwork_count,
                AVG(a.popularity_score) as avg_popularity,
                SUM(a.recognition_count) as total_recognitions
            FROM museums m
            LEFT JOIN artworks a ON m.id = a.museum_id AND a.is_active = true
            WHERE m.is_active = true
            GROUP BY m.id, m.name, m.city, m.country;
            """,
            
            # User activity summary view
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_activity AS
            SELECT 
                DATE(created_at) as activity_date,
                COUNT(*) as new_users,
                COUNT(*) FILTER (WHERE subscription_type != 'free') as premium_users,
                AVG(total_recognitions) as avg_recognitions
            FROM users
            WHERE is_active = true
            GROUP BY DATE(created_at)
            ORDER BY activity_date DESC;
            """
        ]
        
        try:
            with engine.connect() as conn:
                for view_sql in views:
                    try:
                        await asyncio.to_thread(conn.execute, text(view_sql))
                        logger.info(f"Created materialized view: {view_sql[:50]}...")
                    except Exception as e:
                        logger.warning(f"Materialized view creation failed: {e}")
                        
            logger.info("Materialized views created successfully")
            
        except Exception as e:
            logger.error(f"Materialized view creation failed: {e}")
    
    async def refresh_materialized_views(self):
        """Refresh materialized views (should be called periodically)"""
        views_to_refresh = [
            "mv_popular_artworks",
            "mv_museum_stats", 
            "mv_user_activity"
        ]
        
        try:
            with engine.connect() as conn:
                for view_name in views_to_refresh:
                    refresh_sql = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name};"
                    try:
                        await asyncio.to_thread(conn.execute, text(refresh_sql))
                        logger.debug(f"Refreshed materialized view: {view_name}")
                    except Exception as e:
                        logger.warning(f"Failed to refresh view {view_name}: {e}")
                        
        except Exception as e:
            logger.error(f"Materialized view refresh failed: {e}")

# Optimized query builders
class OptimizedQueries:
    """High-performance, cached query builders"""
    
    @staticmethod
    async def get_popular_artworks(limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get popular artworks using materialized view"""
        cache_key = get_cache_key("popular_artworks", str(limit), str(offset))
        
        # Try cache first
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            return cached_result
        
        query = """
        SELECT * FROM mv_popular_artworks 
        LIMIT :limit OFFSET :offset
        """
        
        try:
            with engine.connect() as conn:
                result = await asyncio.to_thread(
                    conn.execute, 
                    text(query), 
                    {"limit": limit, "offset": offset}
                )
                artworks = [dict(row._mapping) for row in result]
                
                # Cache for 5 minutes
                await redis_client.set(cache_key, artworks, ttl=300)
                return artworks
                
        except Exception as e:
            logger.error(f"Failed to get popular artworks: {e}")
            return []
    
    @staticmethod
    async def search_artworks_optimized(
        query: str, 
        museum_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Optimized artwork search using full-text search"""
        cache_key = get_cache_key("artwork_search", query, str(museum_id), str(limit), str(offset))
        
        # Try cache first
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            return cached_result
        
        # Use PostgreSQL full-text search for performance
        search_query = """
        SELECT 
            a.id,
            a.name,
            a.artist,
            a.museum_id,
            a.popularity_score,
            a.recognition_count,
            ts_rank(to_tsvector('english', coalesce(a.name, '') || ' ' || coalesce(a.artist, '')), 
                   plainto_tsquery('english', :query)) as rank
        FROM artworks a
        WHERE a.is_active = true
        AND to_tsvector('english', coalesce(a.name, '') || ' ' || coalesce(a.artist, '')) 
            @@ plainto_tsquery('english', :query)
        {}
        ORDER BY rank DESC, a.popularity_score DESC
        LIMIT :limit OFFSET :offset
        """.format("AND a.museum_id = :museum_id" if museum_id else "")
        
        params = {
            "query": query,
            "limit": limit,
            "offset": offset
        }
        if museum_id:
            params["museum_id"] = museum_id
        
        try:
            with engine.connect() as conn:
                result = await asyncio.to_thread(
                    conn.execute, 
                    text(search_query), 
                    params
                )
                artworks = [dict(row._mapping) for row in result]
                
                # Cache for 2 minutes (shorter TTL for search results)
                await redis_client.set(cache_key, artworks, ttl=120)
                return artworks
                
        except Exception as e:
            logger.error(f"Failed to search artworks: {e}")
            return []
    
    @staticmethod
    async def get_user_with_quota(email: str) -> Optional[Dict[str, Any]]:
        """Optimized user lookup with quota information"""
        cache_key = get_cache_key("user_quota", email)
        
        # Try cache first
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            return cached_result
        
        query = """
        SELECT id, email, username, subscription_type, free_quota, total_recognitions, is_active
        FROM users 
        WHERE email = :email AND is_active = true
        """
        
        try:
            with engine.connect() as conn:
                result = await asyncio.to_thread(
                    conn.execute, 
                    text(query), 
                    {"email": email}
                )
                user_row = result.fetchone()
                
                if user_row:
                    user_data = dict(user_row._mapping)
                    # Cache for 5 minutes
                    await redis_client.set(cache_key, user_data, ttl=300)
                    return user_data
                    
                return None
                
        except Exception as e:
            logger.error(f"Failed to get user with quota: {e}")
            return None

# Connection pool optimization
class OptimizedConnectionPool:
    """Optimized database connection pool configuration"""
    
    @staticmethod
    def configure_engine():
        """Configure engine with optimized settings"""
        # Engine configuration for maximum performance
        engine.pool_size = 20           # Base connections
        engine.max_overflow = 40        # Additional connections
        engine.pool_pre_ping = True     # Validate connections
        engine.pool_recycle = 3600      # Recycle connections every hour
        
        logger.info(f"Database pool configured: {engine.pool_size} base + {engine.pool_overflow} overflow")

# Query monitoring
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Monitor query execution time"""
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log slow queries"""
    total_time = time.time() - context._query_start_time
    
    if total_time > 0.1:  # Log queries slower than 100ms
        logger.warning(
            f"Slow query detected: {total_time:.3f}s - {statement[:100]}...",
            extra={
                "query_time": total_time,
                "statement": statement[:200]
            }
        )

# Global optimizer instance
db_optimizer = DatabaseOptimizer()

# Startup optimization function
async def optimize_database_performance():
    """Run all database optimizations on startup"""
    logger.info("Starting database performance optimization")
    
    try:
        # Configure connection pool
        OptimizedConnectionPool.configure_engine()
        
        # Create optimized indexes
        await db_optimizer.optimize_indexes()
        
        # Create materialized views
        await db_optimizer.create_materialized_views()
        
        logger.info("Database performance optimization completed successfully")
        
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")

# Periodic maintenance task
async def periodic_database_maintenance():
    """Periodic database maintenance tasks"""
    while True:
        try:
            # Refresh materialized views every 15 minutes
            await db_optimizer.refresh_materialized_views()
            
            # Analyze table statistics every hour
            if int(time.time()) % 3600 == 0:
                with engine.connect() as conn:
                    await asyncio.to_thread(conn.execute, text("ANALYZE;"))
                logger.info("Database statistics updated")
            
            await asyncio.sleep(900)  # 15 minutes
            
        except Exception as e:
            logger.error(f"Database maintenance error: {e}")
            await asyncio.sleep(1800)  # Wait 30 minutes on error