from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis_client import init_redis, close_redis
from app.core.logging import setup_logging, get_logger
from app.core.tasks import start_task_workers, stop_task_workers
from app.core.metrics import start_metrics_collection
from app.core.cache_strategy import start_cache_optimization
from app.core.container import initialize_container, cleanup_container
from app.core.exceptions import ExceptionHandlerMiddleware
from app.core.token_manager import start_token_cleanup_task
from app.core.middleware import (
    MetricsMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware, HealthCheckMiddleware
)
# Performance optimization imports
from app.core.database_performance import optimize_database_performance, periodic_database_maintenance
from app.core.redis_performance import initialize_high_performance_redis
from app.core.api_performance import (
    configure_api_performance, response_cache_middleware, 
    ResponseCompressionMiddleware
)
from app.core.memory_optimization import initialize_memory_optimization
from app.core.migrations import initialize_database
from app.api.v1 import recognition, explanation, user, health, auth, tasks, monitoring
import demo_recognition

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Create database tables
# Note: In production, use Alembic migrations instead
# Base.metadata.create_all(bind=engine)

def create_app() -> FastAPI:
    app = FastAPI(
        title="GoMuseum API",
        description="AI-powered museum guide API",
        version="1.0.0",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url="/redoc" if settings.environment == "development" else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_hosts,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted hosts middleware
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=settings.allowed_hosts
    )
    
    # Performance optimization middleware (order matters - last added is executed first)
    app.add_middleware(ResponseCompressionMiddleware, minimum_size=512)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_size=10 * 1024 * 1024)  # 10MB
    app.add_middleware(RateLimitMiddleware, calls=1000, period=3600)  # 1000 requests per hour
    app.add_middleware(HealthCheckMiddleware)
    app.add_middleware(ExceptionHandlerMiddleware)  # Global exception handling
    
    # Configure response caching middleware
    response_cache_middleware.app = app

    # Include routers
    app.include_router(
        health.router,
        tags=["health"]
    )
    
    app.include_router(
        auth.router,
        prefix="/api/v1",
        tags=["authentication"]
    )
    
    app.include_router(
        recognition.router,
        prefix="/api/v1",
        tags=["recognition"]
    )
    
    app.include_router(
        explanation.router,
        prefix="/api/v1",
        tags=["explanation"]
    )
    
    app.include_router(
        user.router,
        prefix="/api/v1",
        tags=["user"]
    )
    
    app.include_router(
        tasks.router,
        prefix="/api/v1",
        tags=["tasks"]
    )
    
    app.include_router(
        monitoring.router,
        prefix="/api/v1",
        tags=["monitoring"]
    )
    
    # 演示识别API (临时用于Step 2)
    app.include_router(
        demo_recognition.router,
        tags=["demo"]
    )

    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup with performance optimizations"""
        logger.info("GoMuseum API starting up", extra={"environment": settings.environment})
        
        # Initialize dependency injection container
        logger.info("Initializing dependency injection container...")
        await initialize_container()
        logger.info("Dependency injection container initialized")
        
        # Initialize database and run migrations
        logger.info("Initializing database...")
        await initialize_database()
        logger.info("Database initialized")
        
        # Initialize performance optimizations
        logger.info("Initializing performance optimizations...")
        
        # Initialize memory optimization
        await initialize_memory_optimization()
        logger.info("Memory optimization initialized")
        
        # Initialize Redis with high-performance settings
        try:
            await init_redis()
            # 临时跳过高性能Redis初始化，用于Step 2快速集成
            # await initialize_high_performance_redis(settings.redis_url)
            logger.info("Basic Redis initialized (high-performance Redis skipped for Step 2)")
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}, continuing without Redis cache")
        
        # Optimize database performance
        await optimize_database_performance()
        logger.info("Database performance optimized")
        
        # Configure API performance settings
        configure_api_performance()
        logger.info("API performance configured")
        
        # Start background task workers
        await start_task_workers()
        logger.info("Background task workers started")
        
        # Start metrics collection
        import asyncio
        asyncio.create_task(start_metrics_collection())
        logger.info("Metrics collection started")
        
        # Start cache optimization
        asyncio.create_task(start_cache_optimization())
        logger.info("Cache optimization started")
        
        # Start periodic database maintenance
        asyncio.create_task(periodic_database_maintenance())
        logger.info("Database maintenance scheduled")
        
        # Start token cleanup task
        asyncio.create_task(start_token_cleanup_task())
        logger.info("Token cleanup task started")
        
        logger.info("🚀 GoMuseum API fully optimized and ready for high-performance operation!")
        
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown"""
        logger.info("GoMuseum API shutting down")
        
        # Stop background task workers
        await stop_task_workers()
        logger.info("Background task workers stopped")
        
        # Cleanup dependency injection container
        await cleanup_container()
        logger.info("Dependency injection container cleaned up")
        
        await close_redis()

    return app

# Create app instance
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )