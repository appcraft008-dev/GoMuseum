"""
Dependency Injection Container
依赖注入容器，实现控制反转和解耦
"""

from typing import AsyncGenerator, Optional, Dict, Any
from functools import lru_cache
import asyncio

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import redis_client
from app.core.cache_strategy import cache_manager
from app.core.logging import get_logger
from app.repositories.recognition_repository import RecognitionRepository
from app.repositories.artwork_repository import ArtworkRepository
from app.repositories.base import BaseRepository
from app.services.ai_service.enhanced_model_selector import EnhancedModelSelector
from app.services.image_processing.image_processor import ImageProcessor
from app.services.ai_service.monitoring import ai_monitor

logger = get_logger(__name__)


class DIContainer:
    """依赖注入容器"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self._services: Dict[str, Any] = {}
            self._repositories: Dict[str, Any] = {}
            self._singletons: Dict[str, Any] = {}
            self.initialized = True
    
    def register_singleton(self, name: str, instance: Any):
        """注册单例服务"""
        self._singletons[name] = instance
        logger.info(f"Registered singleton: {name}")
    
    def get_singleton(self, name: str) -> Optional[Any]:
        """获取单例服务"""
        return self._singletons.get(name)
    
    async def get_or_create_singleton(self, name: str, factory):
        """获取或创建单例服务（线程安全）"""
        if name in self._singletons:
            return self._singletons[name]
        
        async with self._lock:
            # 双重检查
            if name in self._singletons:
                return self._singletons[name]
            
            instance = await factory() if asyncio.iscoroutinefunction(factory) else factory()
            self._singletons[name] = instance
            logger.info(f"Created singleton: {name}")
            return instance


# 全局容器实例
container = DIContainer()


# 初始化单例服务
def initialize_singletons():
    """初始化所有单例服务"""
    # AI服务组件
    container.register_singleton("image_processor", ImageProcessor())
    container.register_singleton("model_selector", EnhancedModelSelector())
    container.register_singleton("ai_monitor", ai_monitor)
    
    # 缓存管理器
    container.register_singleton("cache_manager", cache_manager)
    
    # Redis客户端
    container.register_singleton("redis_client", redis_client)
    
    logger.info("All singletons initialized")


# 依赖注入函数
async def get_recognition_repository(
    db: AsyncSession = Depends(get_db)
) -> RecognitionRepository:
    """获取识别结果仓储"""
    return RecognitionRepository(db)


async def get_artwork_repository(
    db: AsyncSession = Depends(get_db)
) -> ArtworkRepository:
    """获取艺术品仓储"""
    return ArtworkRepository(db)


async def get_image_processor() -> ImageProcessor:
    """获取图像处理器（单例）"""
    return container.get_singleton("image_processor")


async def get_model_selector() -> EnhancedModelSelector:
    """获取模型选择器（单例）"""
    return container.get_singleton("model_selector")


async def get_ai_monitor():
    """获取AI监控器（单例）"""
    return container.get_singleton("ai_monitor")


async def get_cache_manager():
    """获取缓存管理器（单例）"""
    return container.get_singleton("cache_manager")


async def get_redis_client():
    """获取Redis客户端（单例）"""
    return container.get_singleton("redis_client")


# 复合依赖
class RecognitionDependencies:
    """识别服务的所有依赖"""
    
    def __init__(
        self,
        repository: RecognitionRepository,
        image_processor: ImageProcessor,
        model_selector: EnhancedModelSelector,
        ai_monitor: Any,
        cache_manager: Any
    ):
        self.repository = repository
        self.image_processor = image_processor
        self.model_selector = model_selector
        self.ai_monitor = ai_monitor
        self.cache_manager = cache_manager


async def get_recognition_dependencies(
    repository: RecognitionRepository = Depends(get_recognition_repository),
    image_processor: ImageProcessor = Depends(get_image_processor),
    model_selector: EnhancedModelSelector = Depends(get_model_selector),
    ai_monitor = Depends(get_ai_monitor),
    cache_manager = Depends(get_cache_manager)
) -> RecognitionDependencies:
    """获取识别服务的所有依赖"""
    return RecognitionDependencies(
        repository=repository,
        image_processor=image_processor,
        model_selector=model_selector,
        ai_monitor=ai_monitor,
        cache_manager=cache_manager
    )


# 性能优化：缓存依赖结果
@lru_cache()
def get_cached_dependency(name: str):
    """获取缓存的依赖（用于不变的配置）"""
    return container.get_singleton(name)


# 工厂模式：创建服务实例
class ServiceFactory:
    """服务工厂"""
    
    @staticmethod
    async def create_recognition_service(deps: RecognitionDependencies):
        """创建识别服务实例"""
        from app.services.recognition_service_optimized import OptimizedRecognitionService
        
        return OptimizedRecognitionService(
            repository=deps.repository,
            image_processor=deps.image_processor,
            model_selector=deps.model_selector,
            ai_monitor=deps.ai_monitor,
            cache_manager=deps.cache_manager
        )
    
    @staticmethod
    async def create_explanation_service(
        artwork_repo: ArtworkRepository,
        cache_manager: Any
    ):
        """创建解释服务实例"""
        from app.services.explanation_service import ExplanationService
        
        return ExplanationService(
            artwork_repository=artwork_repo,
            cache_manager=cache_manager
        )


# Unit of Work 模式
class UnitOfWork:
    """工作单元模式，管理事务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._repositories = {}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
    
    @property
    def recognition_repository(self) -> RecognitionRepository:
        if "recognition" not in self._repositories:
            self._repositories["recognition"] = RecognitionRepository(self.db)
        return self._repositories["recognition"]
    
    @property
    def artwork_repository(self) -> ArtworkRepository:
        if "artwork" not in self._repositories:
            self._repositories["artwork"] = ArtworkRepository(self.db)
        return self._repositories["artwork"]
    
    async def commit(self):
        """提交事务"""
        try:
            await self.db.commit()
        except Exception as e:
            await self.rollback()
            raise
    
    async def rollback(self):
        """回滚事务"""
        await self.db.rollback()


async def get_unit_of_work(db: AsyncSession = Depends(get_db)) -> UnitOfWork:
    """获取工作单元"""
    return UnitOfWork(db)


# 性能监控装饰器
def with_performance_monitoring(service_name: str):
    """为服务方法添加性能监控"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import time
            start = time.perf_counter()
            
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                
                # 记录性能指标
                logger.debug(f"{service_name}.{func.__name__} took {elapsed:.2f}ms")
                
                # 慢操作警告
                if elapsed > 200:
                    logger.warning(f"Slow operation: {service_name}.{func.__name__} took {elapsed:.2f}ms")
                
                return result
                
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                logger.error(f"{service_name}.{func.__name__} failed after {elapsed:.2f}ms: {e}")
                raise
        
        return wrapper
    return decorator


# 批处理优化
class BatchProcessor:
    """批处理器，优化批量操作"""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self._pending_items = []
        self._lock = asyncio.Lock()
    
    async def add_item(self, item: Any):
        """添加待处理项"""
        async with self._lock:
            self._pending_items.append(item)
            
            if len(self._pending_items) >= self.batch_size:
                await self._process_batch()
    
    async def _process_batch(self):
        """处理批次"""
        if not self._pending_items:
            return
        
        batch = self._pending_items[:self.batch_size]
        self._pending_items = self._pending_items[self.batch_size:]
        
        # 实际的批处理逻辑
        logger.info(f"Processing batch of {len(batch)} items")
        # TODO: 实现具体的批处理逻辑
    
    async def flush(self):
        """强制处理所有待处理项"""
        async with self._lock:
            while self._pending_items:
                await self._process_batch()


# 连接池管理
class ConnectionPoolManager:
    """数据库连接池管理器"""
    
    def __init__(self, max_connections: int = 20):
        self.max_connections = max_connections
        self._pool = []
        self._active_connections = 0
        self._lock = asyncio.Lock()
    
    async def get_connection(self) -> AsyncSession:
        """获取连接"""
        async with self._lock:
            if self._active_connections >= self.max_connections:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Connection pool exhausted"
                )
            
            self._active_connections += 1
            
        try:
            async for db in get_db():
                return db
        except Exception as e:
            async with self._lock:
                self._active_connections -= 1
            raise
    
    async def release_connection(self, conn: AsyncSession):
        """释放连接"""
        async with self._lock:
            self._active_connections -= 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计"""
        return {
            "max_connections": self.max_connections,
            "active_connections": self._active_connections,
            "available_connections": self.max_connections - self._active_connections,
            "utilization": self._active_connections / self.max_connections * 100
        }


# 全局连接池管理器
connection_pool = ConnectionPoolManager()


# 初始化函数
async def initialize_dependencies():
    """初始化所有依赖"""
    initialize_singletons()
    logger.info("Dependencies initialized successfully")