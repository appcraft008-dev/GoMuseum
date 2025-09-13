"""
Optimized Database Configuration
优化的数据库配置，包含连接池管理和查询优化
"""

import asyncio
import time
from typing import AsyncGenerator, Dict, Any, Optional, List
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OptimizedDatabaseConfig:
    """优化的数据库配置"""
    
    # 连接池配置
    POOL_SIZE = 20  # 连接池大小
    MAX_OVERFLOW = 10  # 最大溢出连接数
    POOL_TIMEOUT = 30  # 获取连接超时（秒）
    POOL_RECYCLE = 3600  # 连接回收时间（秒）
    POOL_PRE_PING = True  # 连接前ping检查
    
    # 查询优化配置
    STATEMENT_TIMEOUT = "10s"  # 语句超时
    LOCK_TIMEOUT = "5s"  # 锁超时
    IDLE_IN_TRANSACTION_TIMEOUT = "30s"  # 事务空闲超时
    
    # 性能配置
    ENABLE_QUERY_CACHE = True  # 启用查询缓存
    ENABLE_PREPARED_STATEMENTS = True  # 启用预编译语句
    CONNECTION_MAX_AGE = 600  # 连接最大年龄（秒）


# 创建优化的数据库引擎
def create_optimized_engine():
    """创建优化的数据库引擎"""
    
    # 构建连接参数
    connect_args = {
        "server_settings": {
            "application_name": "gomuseum_api",
            "jit": "off",  # 对于小查询关闭JIT
            "statement_timeout": OptimizedDatabaseConfig.STATEMENT_TIMEOUT,
            "lock_timeout": OptimizedDatabaseConfig.LOCK_TIMEOUT,
            "idle_in_transaction_session_timeout": OptimizedDatabaseConfig.IDLE_IN_TRANSACTION_TIMEOUT,
        },
        "command_timeout": 60,
        "prepared_statement_cache_size": 100 if OptimizedDatabaseConfig.ENABLE_PREPARED_STATEMENTS else 0,
    }
    
    # 创建引擎
    engine = create_async_engine(
        settings.database_url,
        pool_size=OptimizedDatabaseConfig.POOL_SIZE,
        max_overflow=OptimizedDatabaseConfig.MAX_OVERFLOW,
        pool_timeout=OptimizedDatabaseConfig.POOL_TIMEOUT,
        pool_recycle=OptimizedDatabaseConfig.POOL_RECYCLE,
        pool_pre_ping=OptimizedDatabaseConfig.POOL_PRE_PING,
        echo=False,  # 生产环境关闭SQL日志
        connect_args=connect_args,
        pool_class=QueuePool,  # 使用队列池
    )
    
    logger.info(f"Created optimized database engine with pool size {OptimizedDatabaseConfig.POOL_SIZE}")
    
    return engine


# 全局引擎实例
optimized_engine = create_optimized_engine()

# 创建会话工厂
OptimizedAsyncSessionLocal = async_sessionmaker(
    optimized_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # 关闭自动flush提升性能
    autocommit=False
)


class ConnectionPoolManager:
    """连接池管理器"""
    
    def __init__(self, engine):
        self.engine = engine
        self.pool = engine.pool
        self._stats = {
            "connections_created": 0,
            "connections_recycled": 0,
            "connections_failed": 0,
            "slow_queries": []
        }
        self._connection_semaphore = asyncio.Semaphore(OptimizedDatabaseConfig.POOL_SIZE)
        
    async def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        try:
            pool = self.engine.pool
            return {
                "size": pool.size() if hasattr(pool, 'size') else OptimizedDatabaseConfig.POOL_SIZE,
                "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else 0,
                "checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else 0,
                "overflow": pool.overflow() if hasattr(pool, 'overflow') else 0,
                "total": pool.total() if hasattr(pool, 'total') else 0,
                "stats": self._stats
            }
        except Exception as e:
            logger.error(f"Failed to get pool status: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def optimize_pool(self):
        """优化连接池"""
        logger.info("Optimizing database connection pool")
        
        try:
            # 回收空闲连接
            await self.engine.dispose()
            
            # 重新创建连接
            self.engine = create_optimized_engine()
            
            # 预热连接池
            await self._warm_pool()
            
            self._stats["connections_recycled"] += OptimizedDatabaseConfig.POOL_SIZE
            logger.info("Connection pool optimized successfully")
            
        except Exception as e:
            logger.error(f"Failed to optimize pool: {e}")
            self._stats["connections_failed"] += 1
    
    async def _warm_pool(self):
        """预热连接池"""
        tasks = []
        for _ in range(min(5, OptimizedDatabaseConfig.POOL_SIZE)):
            tasks.append(self._create_connection())
        
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Warmed up {len(tasks)} connections")
    
    async def _create_connection(self):
        """创建单个连接"""
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            self._stats["connections_created"] += 1
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            self._stats["connections_failed"] += 1
    
    def record_slow_query(self, query: str, duration_ms: float):
        """记录慢查询"""
        self._stats["slow_queries"].append({
            "query": query[:200],  # 截断长查询
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # 只保留最近100条慢查询
        if len(self._stats["slow_queries"]) > 100:
            self._stats["slow_queries"] = self._stats["slow_queries"][-100:]


# 全局连接池管理器
pool_manager = ConnectionPoolManager(optimized_engine)


class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self):
        self.query_cache = {}
        self.prepared_statements = {}
        
    async def execute_optimized(
        self,
        session: AsyncSession,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Any:
        """执行优化的查询"""
        start_time = time.perf_counter()
        
        # 生成缓存键
        cache_key = f"{query}:{str(params)}" if params else query
        
        # 检查缓存
        if use_cache and cache_key in self.query_cache:
            cache_entry = self.query_cache[cache_key]
            if cache_entry["expires"] > datetime.utcnow():
                logger.debug(f"Query cache hit for: {query[:50]}...")
                return cache_entry["result"]
        
        try:
            # 执行查询
            if params:
                result = await session.execute(text(query), params)
            else:
                result = await session.execute(text(query))
            
            # 获取结果
            data = result.fetchall() if result.returns_rows else None
            
            # 记录执行时间
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # 记录慢查询
            if duration_ms > 100:  # 100ms阈值
                pool_manager.record_slow_query(query, duration_ms)
                logger.warning(f"Slow query detected ({duration_ms:.2f}ms): {query[:100]}...")
            
            # 缓存结果
            if use_cache and data is not None:
                self.query_cache[cache_key] = {
                    "result": data,
                    "expires": datetime.utcnow() + timedelta(minutes=5)
                }
                
                # 限制缓存大小
                if len(self.query_cache) > 1000:
                    # 删除最旧的缓存项
                    oldest_key = min(self.query_cache.keys(), 
                                   key=lambda k: self.query_cache[k]["expires"])
                    del self.query_cache[oldest_key]
            
            return data
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Query failed after {duration_ms:.2f}ms: {e}")
            raise
    
    async def bulk_insert_optimized(
        self,
        session: AsyncSession,
        table_name: str,
        records: List[Dict[str, Any]]
    ) -> int:
        """优化的批量插入"""
        if not records:
            return 0
        
        # 构建批量插入语句
        columns = list(records[0].keys())
        placeholders = [f":{col}" for col in columns]
        
        query = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """
        
        # 批量执行
        batch_size = 1000
        inserted = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            try:
                # 使用executemany for批量插入
                for record in batch:
                    await session.execute(text(query), record)
                
                inserted += len(batch)
                
                # 定期提交
                if inserted % 5000 == 0:
                    await session.commit()
                    
            except Exception as e:
                logger.error(f"Bulk insert failed at batch {i}: {e}")
                await session.rollback()
                raise
        
        await session.commit()
        logger.info(f"Bulk inserted {inserted} records into {table_name}")
        
        return inserted
    
    def clear_cache(self):
        """清除查询缓存"""
        self.query_cache.clear()
        logger.info("Query cache cleared")


# 全局查询优化器
query_optimizer = QueryOptimizer()


# 优化的数据库会话获取
@asynccontextmanager
async def get_optimized_db() -> AsyncGenerator[AsyncSession, None]:
    """获取优化的数据库会话"""
    async with pool_manager._connection_semaphore:  # 限制并发连接
        async with OptimizedAsyncSessionLocal() as session:
            try:
                # 设置会话级优化
                await session.execute(text("SET work_mem = '256MB'"))
                await session.execute(text("SET random_page_cost = 1.1"))
                
                yield session
                
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()


# 数据库索引优化建议
class IndexAdvisor:
    """索引优化顾问"""
    
    @staticmethod
    async def analyze_missing_indexes(session: AsyncSession) -> List[Dict[str, Any]]:
        """分析缺失的索引"""
        query = """
            SELECT 
                schemaname,
                tablename,
                attname,
                n_distinct,
                avg_width,
                correlation
            FROM pg_stats
            WHERE schemaname = 'public'
                AND n_distinct > 100
                AND correlation < 0.5
                AND correlation > -0.5
            ORDER BY n_distinct DESC
            LIMIT 20
        """
        
        result = await session.execute(text(query))
        
        recommendations = []
        for row in result:
            recommendations.append({
                "table": f"{row[0]}.{row[1]}",
                "column": row[2],
                "distinct_values": row[3],
                "avg_width": row[4],
                "correlation": row[5],
                "recommendation": f"CREATE INDEX idx_{row[1]}_{row[2]} ON {row[0]}.{row[1]} ({row[2]})"
            })
        
        return recommendations
    
    @staticmethod
    async def analyze_unused_indexes(session: AsyncSession) -> List[Dict[str, Any]]:
        """分析未使用的索引"""
        query = """
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
                AND indexrelname NOT LIKE '%_pkey'
            ORDER BY pg_relation_size(indexrelid) DESC
            LIMIT 10
        """
        
        result = await session.execute(text(query))
        
        unused = []
        for row in result:
            unused.append({
                "index": f"{row[0]}.{row[2]}",
                "table": f"{row[0]}.{row[1]}",
                "scans": row[3],
                "size": row[6],
                "recommendation": f"DROP INDEX {row[0]}.{row[2]}"
            })
        
        return unused
    
    @staticmethod
    async def create_index_async(
        session: AsyncSession,
        table: str,
        column: str,
        index_type: str = "btree"
    ):
        """异步创建索引（使用CONCURRENTLY）"""
        index_name = f"idx_{table}_{column}_{int(time.time())}"
        
        query = f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
            ON {table} USING {index_type} ({column})
        """
        
        try:
            await session.execute(text(query))
            await session.commit()
            logger.info(f"Created index {index_name} on {table}.{column}")
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            await session.rollback()
            raise


# 数据库维护任务
async def periodic_database_optimization():
    """定期数据库优化任务"""
    while True:
        try:
            logger.info("Starting periodic database optimization")
            
            async with get_optimized_db() as session:
                # 更新统计信息
                await session.execute(text("ANALYZE"))
                
                # 清理死元组
                await session.execute(text("VACUUM (ANALYZE)"))
                
                # 重建索引（仅对碎片化严重的）
                result = await session.execute(text("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname
                    FROM pg_stat_user_indexes
                    WHERE pg_relation_size(indexrelid) > 10485760  -- 10MB
                    ORDER BY pg_relation_size(indexrelid) DESC
                    LIMIT 5
                """))
                
                for row in result:
                    try:
                        await session.execute(text(f"REINDEX INDEX CONCURRENTLY {row[0]}.{row[2]}"))
                        logger.info(f"Reindexed {row[0]}.{row[2]}")
                    except Exception as e:
                        logger.error(f"Failed to reindex {row[2]}: {e}")
                
                await session.commit()
            
            # 优化连接池
            await pool_manager.optimize_pool()
            
            # 清理查询缓存
            query_optimizer.clear_cache()
            
            logger.info("Database optimization completed")
            
            # 每6小时执行一次
            await asyncio.sleep(21600)
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            await asyncio.sleep(3600)  # 失败后1小时重试


# 导出优化后的数据库接口
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（向后兼容）"""
    async with get_optimized_db() as session:
        yield session