"""
Database configuration and session management
SQLAlchemy setup for PostgreSQL with optimized connection pooling
"""

import logging
import os
import socket
import threading
import time
from datetime import datetime, timezone
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
    note_checkout(engine.pool.checkedout())


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


# ── 连接池在用峰值(spec §7 T2):每进程每分钟的最高值写进 Redis,ops_check 按前缀读 ──
POOL_PEAK_KEY = "ops:pool_peak:{minute}:{proc}"
_pool_peak = 0
_reporter_started = False


def note_checkout(checked_out: int) -> None:
    # ponytail: 不加锁,并发 checkout 时最多少记 1;峰值是趋势指标,不值得在热路径上加锁
    global _pool_peak
    if checked_out > _pool_peak:
        _pool_peak = checked_out


def flush_pool_peak(redis, current: int, now: datetime) -> int | None:
    """写 max(本分钟峰值, current),再把峰值重置成 current(跨分钟仍被占着的连接算进下一分钟)。
    redis 为 None 或报错 → None,不抛。"""
    global _pool_peak
    if redis is None:
        return None
    value = max(_pool_peak, current)
    key = POOL_PEAK_KEY.format(
        minute=now.strftime("%Y%m%d%H%M"), proc=f"{socket.gethostname()}-{os.getpid()}"
    )
    try:
        redis.set(key, value, ex=900)
    except Exception:
        logger.warning("pool peak flush failed", exc_info=True)
        return None
    _pool_peak = current
    return value


def start_pool_peak_reporter() -> None:
    """守护线程每 60 秒上报一次;每进程只起一个。"""
    global _reporter_started
    if _reporter_started:
        return
    _reporter_started = True

    def loop():
        from app.services.recognition.service import _get_redis

        while True:
            time.sleep(60)
            try:
                flush_pool_peak(
                    _get_redis(), engine.pool.checkedout(), datetime.now(timezone.utc)
                )
            except Exception:
                logger.warning("pool peak reporter failed", exc_info=True)

    threading.Thread(target=loop, name="pool-peak", daemon=True).start()
