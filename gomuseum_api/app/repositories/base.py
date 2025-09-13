"""
Base Repository Pattern Implementation
提供数据访问层抽象，优化数据库查询性能
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
import logging

from app.core.database import SessionLocal
from app.core.cache_strategy import cache_manager, CacheStrategy
from app.core.metrics import metrics

logger = logging.getLogger(__name__)

T = TypeVar("T")

class BaseRepository(Generic[T]):
    """
    基础Repository类，提供CRUD操作和查询优化
    实现连接池管理、查询缓存、批量操作等性能优化
    """
    
    def __init__(self, model: Type[T]):
        self.model = model
        self._session_pool = []  # 会话池
        self._prepared_statements = {}  # 预编译语句缓存
        
    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """获取数据库会话，支持连接池"""
        session = SessionLocal()
        try:
            yield session
        finally:
            await session.close()
    
    async def get_by_id(
        self, 
        id: Any, 
        use_cache: bool = True,
        cache_ttl: int = 300
    ) -> Optional[T]:
        """
        通过ID获取实体，支持缓存
        """
        start_time = asyncio.get_event_loop().time()
        
        # 尝试从缓存获取
        if use_cache:
            cache_key = f"{self.model.__tablename__}:{id}"
            cached = await cache_manager.get(cache_key)
            if cached:
                metrics.increment_counter("database_query")
                return cached
        
        # 从数据库获取
        async with self.get_session() as session:
            result = await session.get(self.model, id)
            
            # 缓存结果
            if result and use_cache:
                await cache_manager.set(
                    f"{self.model.__tablename__}:{id}",
                    result,
                    ttl=cache_ttl,
                    strategy=CacheStrategy.WRITE_THROUGH
                )
            
            metrics.increment_counter(self.model.__tablename__, "select", 
                               asyncio.get_event_loop().time() - start_time)
            return result
    
    async def get_many(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        use_cache: bool = True
    ) -> List[T]:
        """
        获取多个实体，支持过滤、排序、分页和缓存
        """
        start_time = asyncio.get_event_loop().time()
        
        # 构建缓存键
        if use_cache:
            cache_key = self._build_cache_key("get_many", filters, order_by, limit, offset)
            cached = await cache_manager.get(cache_key)
            if cached:
                metrics.increment_counter(self.model.__tablename__, "cache_hit",
                                   asyncio.get_event_loop().time() - start_time)
                return cached
        
        # 构建查询
        async with self.get_session() as session:
            query = select(self.model)
            
            # 应用过滤器
            if filters:
                conditions = []
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        conditions.append(getattr(self.model, key) == value)
                if conditions:
                    query = query.where(and_(*conditions))
            
            # 应用排序
            if order_by:
                if order_by.startswith("-"):
                    query = query.order_by(getattr(self.model, order_by[1:]).desc())
                else:
                    query = query.order_by(getattr(self.model, order_by))
            
            # 应用分页
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
            
            # 执行查询
            result = await session.execute(query)
            items = result.scalars().all()
            
            # 缓存结果
            if use_cache and items:
                await cache_manager.set(
                    cache_key,
                    items,
                    ttl=300,
                    strategy=CacheStrategy.WRITE_THROUGH
                )
            
            metrics.increment_counter(self.model.__tablename__, "select_many",
                               asyncio.get_event_loop().time() - start_time)
            return items
    
    async def create(
        self,
        data: Dict[str, Any],
        refresh: bool = True
    ) -> T:
        """
        创建实体，支持自动刷新
        """
        start_time = asyncio.get_event_loop().time()
        
        async with self.get_session() as session:
            instance = self.model(**data)
            session.add(instance)
            await session.commit()
            
            if refresh:
                await session.refresh(instance)
            
            # 使缓存失效
            await self._invalidate_cache()
            
            metrics.increment_counter(self.model.__tablename__, "insert",
                               asyncio.get_event_loop().time() - start_time)
            return instance
    
    async def bulk_create(
        self,
        items: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> List[T]:
        """
        批量创建实体，优化大量插入性能
        """
        start_time = asyncio.get_event_loop().time()
        created_items = []
        
        async with self.get_session() as session:
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                instances = [self.model(**data) for data in batch]
                session.add_all(instances)
                await session.commit()
                created_items.extend(instances)
            
            # 使缓存失效
            await self._invalidate_cache()
            
            metrics.increment_counter(self.model.__tablename__, "bulk_insert",
                               asyncio.get_event_loop().time() - start_time)
            return created_items
    
    async def update(
        self,
        id: Any,
        data: Dict[str, Any]
    ) -> Optional[T]:
        """
        更新实体
        """
        start_time = asyncio.get_event_loop().time()
        
        async with self.get_session() as session:
            instance = await session.get(self.model, id)
            if not instance:
                return None
            
            for key, value in data.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            
            await session.commit()
            await session.refresh(instance)
            
            # 更新缓存
            cache_key = f"{self.model.__tablename__}:{id}"
            await cache_manager.set(
                cache_key,
                instance,
                ttl=300,
                strategy=CacheStrategy.WRITE_THROUGH
            )
            
            metrics.increment_counter(self.model.__tablename__, "update",
                               asyncio.get_event_loop().time() - start_time)
            return instance
    
    async def delete(self, id: Any) -> bool:
        """
        删除实体
        """
        start_time = asyncio.get_event_loop().time()
        
        async with self.get_session() as session:
            instance = await session.get(self.model, id)
            if not instance:
                return False
            
            await session.delete(instance)
            await session.commit()
            
            # 删除缓存
            cache_key = f"{self.model.__tablename__}:{id}"
            await cache_manager.delete(cache_key)
            
            metrics.increment_counter(self.model.__tablename__, "delete",
                               asyncio.get_event_loop().time() - start_time)
            return True
    
    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        计数查询，支持过滤
        """
        start_time = asyncio.get_event_loop().time()
        
        async with self.get_session() as session:
            query = select(func.count()).select_from(self.model)
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        conditions.append(getattr(self.model, key) == value)
                if conditions:
                    query = query.where(and_(*conditions))
            
            result = await session.execute(query)
            count = result.scalar()
            
            metrics.increment_counter(self.model.__tablename__, "count",
                               asyncio.get_event_loop().time() - start_time)
            return count
    
    async def exists(
        self,
        filters: Dict[str, Any]
    ) -> bool:
        """
        检查是否存在
        """
        count = await self.count(filters)
        return count > 0
    
    def _build_cache_key(self, operation: str, *args, **kwargs) -> str:
        """
        构建缓存键
        """
        key_parts = [self.model.__tablename__, operation]
        for arg in args:
            if arg is not None:
                key_parts.append(str(arg))
        for k, v in kwargs.items():
            if v is not None:
                key_parts.append(f"{k}:{v}")
        return ":".join(key_parts)
    
    async def _invalidate_cache(self):
        """
        使相关缓存失效
        """
        # 这里可以实现更智能的缓存失效策略
        pattern = f"{self.model.__tablename__}:*"
        # 在实际实现中，应该使用Redis的SCAN命令来查找和删除匹配的键
        logger.debug(f"Invalidating cache for pattern: {pattern}")
    
    async def execute_raw(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        执行原始SQL查询，用于复杂查询优化
        """
        start_time = asyncio.get_event_loop().time()
        
        async with self.get_session() as session:
            result = await session.execute(query, params or {})
            
            metrics.increment_counter("raw_query", "execute",
                               asyncio.get_event_loop().time() - start_time)
            return result