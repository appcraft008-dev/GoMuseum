"""
Database configuration and session management
SQLAlchemy setup for PostgreSQL with optimized connection pooling
"""

import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with optimized connection pool settings
# Pool configuration optimized for high-concurrency workloads:
# - pool_size: 20 connections (increased from 10)
# - max_overflow: 40 additional connections under load (increased from 20)
# - pool_pre_ping: Verify connections before use (prevents stale connections)
# - pool_recycle: Recycle connections after 1 hour (prevents long-lived connection issues)
# - pool_timeout: Wait up to 30 seconds for available connection
# - echo: Log SQL queries in debug mode
engine = create_engine(
    settings.get_database_url(),
    pool_pre_ping=True,
    pool_size=20,  # Base pool size for normal operations
    max_overflow=40,  # Allow up to 60 total connections under peak load
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_timeout=30,  # Wait up to 30 seconds for connection
    echo=settings.DEBUG,
    # Additional PostgreSQL-specific optimizations
    connect_args={"options": "-c statement_timeout=30000"},  # 30 second query timeout
)


# Event listener to log connection pool statistics
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log when new database connections are established"""
    logger.debug("Database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log when connections are checked out from the pool"""
    logger.debug(
        f"Connection checked out from pool. Pool status: {engine.pool.status()}"
    )


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log when connections are returned to the pool"""
    logger.debug("Connection returned to pool")


def audio_loss_guard(session, flush_context, instances):
    """音频损失闸(契约纪律 37),挂在每个 guarded_sessionmaker 上。
    延迟导入:app.services 包的 __init__ 会拉一串服务模块,在这里顶层导入会循环。"""
    from app.services.audio_guard import on_flush

    on_flush(session)


def guarded_sessionmaker(**kw):
    """**应用与脚本里唯一允许的 sessionmaker 入口**:建出来的会话自动挂音频损失闸。

    曾有线程池另起 `sessionmaker(bind=...)`(补语种 backfill_languages),那条路径就
    绕过了闸 —— 所以不许直接调 sessionmaker,由 tests/unit/test_no_bare_sessionmaker.py 钉住。
    """
    factory = sessionmaker(**kw)
    event.listen(factory, "before_flush", audio_loss_guard)
    return factory


# Create SessionLocal class(web 与所有脚本共用;带音频损失闸)
SessionLocal = guarded_sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Create Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Database dependency for FastAPI
    Yields a database session and ensures it's closed after use
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables
    Creates all tables defined in models
    """
    Base.metadata.create_all(bind=engine)
