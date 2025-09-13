"""
Artwork Repository Implementation
优化艺术品数据访问，提供高性能查询和缓存
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import joinedload, selectinload
import asyncio

from app.repositories.base import BaseRepository
from app.models.artwork import Artwork
from app.core.cache_strategy import cache_manager, CacheStrategy
from app.core.metrics import metrics
import logging

logger = logging.getLogger(__name__)

class ArtworkRepository(BaseRepository[Artwork]):
    """
    艺术品数据访问层
    实现特定的查询优化和缓存策略
    """
    
    def __init__(self):
        super().__init__(Artwork)
        self._popular_cache_ttl = 3600  # 热门艺术品缓存1小时
        self._search_cache_ttl = 1800   # 搜索结果缓存30分钟
    
    async def get_popular_artworks(
        self,
        museum_id: Optional[str] = None,
        limit: int = 50,
        use_cache: bool = True
    ) -> List[Artwork]:
        """
        获取热门艺术品，优化查询性能
        使用物化视图和智能缓存
        """
        start_time = asyncio.get_event_loop().time()
        
        # 构建缓存键
        cache_key = f"artworks:popular:{museum_id or 'all'}:{limit}"
        
        # 尝试从缓存获取
        if use_cache:
            cached = await cache_manager.get(cache_key)
            if cached:
                track_database_query("artworks", "popular_cache_hit",
                                   asyncio.get_event_loop().time() - start_time)
                return cached
        
        # 使用优化的查询
        async with self.get_session() as session:
            # 首先尝试使用物化视图
            try:
                if museum_id:
                    query = """
                        SELECT * FROM mv_popular_artworks 
                        WHERE museum_id = :museum_id
                        LIMIT :limit
                    """
                    result = await session.execute(
                        query, 
                        {"museum_id": museum_id, "limit": limit}
                    )
                else:
                    query = """
                        SELECT * FROM mv_popular_artworks 
                        LIMIT :limit
                    """
                    result = await session.execute(
                        query,
                        {"limit": limit}
                    )
                
                artworks = result.fetchall()
                
            except Exception as e:
                # 物化视图不存在或失败，使用常规查询
                logger.warning(f"Materialized view query failed: {e}")
                
                query = select(Artwork).where(Artwork.is_active == True)
                
                if museum_id:
                    query = query.where(Artwork.museum_id == museum_id)
                
                query = query.order_by(
                    desc(Artwork.popularity_score),
                    desc(Artwork.recognition_count)
                ).limit(limit)
                
                # 使用预加载优化关联查询
                query = query.options(selectinload(Artwork.museum))
                
                result = await session.execute(query)
                artworks = result.scalars().all()
            
            # 缓存结果，标记为热门
            if use_cache and artworks:
                await cache_manager.set(
                    cache_key,
                    artworks,
                    ttl=self._popular_cache_ttl,
                    tags=["popular", "artworks"],
                    is_popular=True,  # 标记为热门内容
                    strategy=CacheStrategy.REFRESH_AHEAD  # 提前刷新策略
                )
                
                # 将热门艺术品的ID加入热门集合
                popular_keys = [f"artwork:{a.id}" for a in artworks[:10]]
                cache_manager.mark_popular_items(popular_keys)
            
            track_database_query("artworks", "popular_select",
                               asyncio.get_event_loop().time() - start_time)
            return artworks
    
    async def search_artworks(
        self,
        query: str,
        museum_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Artwork]:
        """
        全文搜索艺术品，使用PostgreSQL全文搜索和缓存
        """
        start_time = asyncio.get_event_loop().time()
        
        # 构建缓存键
        cache_key = f"artworks:search:{query}:{museum_id or 'all'}:{limit}:{offset}"
        
        # 尝试从缓存获取
        cached = await cache_manager.get(cache_key)
        if cached:
            track_database_query("artworks", "search_cache_hit",
                               asyncio.get_event_loop().time() - start_time)
            return cached
        
        async with self.get_session() as session:
            # 使用PostgreSQL全文搜索
            search_query = """
                SELECT a.*, 
                       ts_rank(search_vector, plainto_tsquery('english', :query)) as rank
                FROM artworks a
                WHERE a.is_active = true
                  AND search_vector @@ plainto_tsquery('english', :query)
            """
            
            if museum_id:
                search_query += " AND a.museum_id = :museum_id"
            
            search_query += """
                ORDER BY rank DESC, a.popularity_score DESC
                LIMIT :limit OFFSET :offset
            """
            
            params = {
                "query": query,
                "limit": limit,
                "offset": offset
            }
            if museum_id:
                params["museum_id"] = museum_id
            
            result = await session.execute(search_query, params)
            artworks = result.fetchall()
            
            # 缓存搜索结果
            if artworks:
                await cache_manager.set(
                    cache_key,
                    artworks,
                    ttl=self._search_cache_ttl,
                    tags=["search", "artworks"],
                    strategy=CacheStrategy.WRITE_THROUGH
                )
            
            track_database_query("artworks", "search",
                               asyncio.get_event_loop().time() - start_time)
            return artworks
    
    async def get_by_recognition_hash(
        self,
        image_hash: str,
        confidence_threshold: float = 0.8
    ) -> Optional[Artwork]:
        """
        通过识别哈希获取艺术品，使用缓存优化
        """
        cache_key = f"artwork:recognition:{image_hash}"
        
        # 优先从缓存获取
        cached = await cache_manager.get(cache_key)
        if cached:
            return cached
        
        async with self.get_session() as session:
            # 查询识别缓存表
            query = """
                SELECT a.* 
                FROM artworks a
                JOIN recognition_cache rc ON rc.artwork_id = a.id
                WHERE rc.image_hash = :image_hash
                  AND rc.confidence >= :confidence_threshold
                ORDER BY rc.confidence DESC
                LIMIT 1
            """
            
            result = await session.execute(
                query,
                {
                    "image_hash": image_hash,
                    "confidence_threshold": confidence_threshold
                }
            )
            artwork = result.fetchone()
            
            if artwork:
                # 缓存结果
                await cache_manager.set(
                    cache_key,
                    artwork,
                    ttl=3600,
                    strategy=CacheStrategy.WRITE_THROUGH
                )
            
            return artwork
    
    async def increment_recognition_count(
        self,
        artwork_id: str,
        increment: int = 1
    ) -> bool:
        """
        原子性增加识别计数，优化并发更新
        """
        async with self.get_session() as session:
            # 使用原子更新避免并发问题
            query = """
                UPDATE artworks 
                SET recognition_count = recognition_count + :increment,
                    last_recognized_at = NOW(),
                    popularity_score = popularity_score + (:increment * 0.1)
                WHERE id = :artwork_id
                RETURNING id
            """
            
            result = await session.execute(
                query,
                {"artwork_id": artwork_id, "increment": increment}
            )
            await session.commit()
            
            # 使缓存失效
            await cache_manager.delete(f"artwork:{artwork_id}")
            
            return result.rowcount > 0
    
    async def get_nearby_artworks(
        self,
        museum_id: str,
        current_artwork_id: str,
        limit: int = 10
    ) -> List[Artwork]:
        """
        获取同一博物馆的相近艺术品，用于预加载
        """
        cache_key = f"artworks:nearby:{museum_id}:{current_artwork_id}:{limit}"
        
        cached = await cache_manager.get(cache_key)
        if cached:
            return cached
        
        async with self.get_session() as session:
            # 获取相同博物馆的其他热门艺术品
            query = select(Artwork).where(
                and_(
                    Artwork.museum_id == museum_id,
                    Artwork.id != current_artwork_id,
                    Artwork.is_active == True
                )
            ).order_by(
                desc(Artwork.popularity_score)
            ).limit(limit)
            
            result = await session.execute(query)
            artworks = result.scalars().all()
            
            # 缓存结果，使用博物馆上下文
            if artworks:
                await cache_manager.set(
                    cache_key,
                    artworks,
                    ttl=1800,
                    museum_id=museum_id,  # 设置博物馆上下文
                    strategy=CacheStrategy.WRITE_THROUGH
                )
            
            return artworks
    
    async def batch_get_by_ids(
        self,
        ids: List[str],
        use_cache: bool = True
    ) -> Dict[str, Artwork]:
        """
        批量获取艺术品，优化N+1查询问题
        """
        result = {}
        uncached_ids = []
        
        # 先从缓存获取
        if use_cache:
            for artwork_id in ids:
                cache_key = f"artwork:{artwork_id}"
                cached = await cache_manager.get(cache_key)
                if cached:
                    result[artwork_id] = cached
                else:
                    uncached_ids.append(artwork_id)
        else:
            uncached_ids = ids
        
        # 批量从数据库获取未缓存的
        if uncached_ids:
            async with self.get_session() as session:
                query = select(Artwork).where(Artwork.id.in_(uncached_ids))
                db_result = await session.execute(query)
                artworks = db_result.scalars().all()
                
                # 更新结果并缓存
                for artwork in artworks:
                    result[artwork.id] = artwork
                    if use_cache:
                        cache_key = f"artwork:{artwork.id}"
                        await cache_manager.set(
                            cache_key,
                            artwork,
                            ttl=600,
                            strategy=CacheStrategy.WRITE_THROUGH
                        )
        
        return result