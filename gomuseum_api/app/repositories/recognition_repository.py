"""
Recognition Repository Layer
实现数据访问抽象，支持缓存和数据库操作
"""

import asyncio
import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
from sqlalchemy import text, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.redis_client import redis_client, get_cache_key
from app.core.cache_strategy import cache_manager, CacheStrategy
from app.models.recognition_cache import RecognitionCache
from app.core.logging import get_logger

logger = get_logger(__name__)

class RecognitionRepository:
    """
    Recognition数据访问层
    职责：
    1. 数据持久化操作
    2. 缓存管理
    3. 批量操作优化
    4. 查询优化
    """
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour default
        self.batch_size = 100
        
    async def get_recognition_result(
        self, 
        image_hash: str,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        获取识别结果
        优先从缓存获取，然后从数据库
        """
        if use_cache:
            # L1 + L2 缓存查询
            cache_key = f"recognition:{image_hash}"
            cached_result = await cache_manager.get(cache_key)
            
            if cached_result:
                logger.debug(f"Cache hit for image {image_hash[:8]}")
                return cached_result
        
        # 数据库查询
        try:
            with SessionLocal() as db:
                query = text("""
                    SELECT 
                        id, image_hash, result_data, confidence,
                        model_used, processing_time, created_at
                    FROM recognition_cache
                    WHERE image_hash = :image_hash
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                result = db.execute(query, {"image_hash": image_hash}).fetchone()
                
                if result:
                    recognition_data = {
                        "id": str(result.id),
                        "image_hash": result.image_hash,
                        "result": json.loads(result.result_data) if result.result_data else {},
                        "confidence": result.confidence,
                        "model_used": result.model_used,
                        "processing_time": result.processing_time,
                        "created_at": result.created_at.isoformat() if result.created_at else None,
                        "cached": True
                    }
                    
                    # 写入缓存
                    if use_cache:
                        await self._cache_recognition_result(image_hash, recognition_data)
                    
                    return recognition_data
                    
        except Exception as e:
            logger.error(f"Database query failed for image {image_hash[:8]}: {e}")
        
        return None
    
    async def save_recognition_result(
        self,
        image_hash: str,
        result_data: Dict[str, Any],
        confidence: float,
        model_used: str,
        processing_time: float
    ) -> bool:
        """
        保存识别结果到数据库和缓存
        使用Write-Through策略
        """
        try:
            # 并发写入数据库和缓存
            db_task = self._save_to_database(
                image_hash, result_data, confidence, 
                model_used, processing_time
            )
            
            cache_task = self._cache_recognition_result(
                image_hash, {
                    "image_hash": image_hash,
                    "result": result_data,
                    "confidence": confidence,
                    "model_used": model_used,
                    "processing_time": processing_time,
                    "created_at": datetime.utcnow().isoformat(),
                    "cached": False
                }
            )
            
            # 并发执行
            db_success, cache_success = await asyncio.gather(
                db_task, cache_task,
                return_exceptions=True
            )
            
            # 检查结果
            if isinstance(db_success, Exception):
                logger.error(f"Database save failed: {db_success}")
                return False
            
            if isinstance(cache_success, Exception):
                logger.warning(f"Cache save failed: {cache_success}")
                # 缓存失败不影响整体结果
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save recognition result: {e}")
            return False
    
    async def _save_to_database(
        self,
        image_hash: str,
        result_data: Dict[str, Any],
        confidence: float,
        model_used: str,
        processing_time: float
    ) -> bool:
        """保存到数据库"""
        try:
            with SessionLocal() as db:
                # 使用UPSERT避免重复
                query = text("""
                    INSERT INTO recognition_cache 
                    (image_hash, result_data, confidence, model_used, processing_time, created_at)
                    VALUES (:image_hash, :result_data, :confidence, :model_used, :processing_time, :created_at)
                    ON CONFLICT (image_hash) 
                    DO UPDATE SET
                        result_data = EXCLUDED.result_data,
                        confidence = EXCLUDED.confidence,
                        model_used = EXCLUDED.model_used,
                        processing_time = EXCLUDED.processing_time,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """)
                
                result = db.execute(query, {
                    "image_hash": image_hash,
                    "result_data": json.dumps(result_data),
                    "confidence": confidence,
                    "model_used": model_used,
                    "processing_time": processing_time,
                    "created_at": datetime.utcnow()
                })
                
                db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Database save error: {e}")
            return False
    
    async def _cache_recognition_result(
        self,
        image_hash: str,
        result_data: Dict[str, Any]
    ) -> bool:
        """缓存识别结果"""
        try:
            cache_key = f"recognition:{image_hash}"
            
            # 判断是否为热门内容
            is_popular = await self._is_popular_content(image_hash)
            
            # 使用多级缓存策略
            success = await cache_manager.set(
                key=cache_key,
                value=result_data,
                ttl=self.cache_ttl * 2 if is_popular else self.cache_ttl,  # 热门内容更长TTL
                strategy=CacheStrategy.WRITE_THROUGH,
                is_popular=is_popular,
                priority=2 if is_popular else 1
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Cache save error: {e}")
            return False
    
    async def _is_popular_content(self, image_hash: str) -> bool:
        """判断是否为热门内容"""
        try:
            # 获取访问计数
            count_key = get_cache_key("recognition_count", image_hash)
            count = await redis_client.get(count_key) or 0
            
            # 增加计数
            await redis_client.increment(count_key)
            
            # 热门阈值：访问超过10次
            return int(count) > 10
            
        except Exception:
            return False
    
    async def batch_get_recognition_results(
        self,
        image_hashes: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量获取识别结果
        优化：减少数据库往返
        """
        results = {}
        uncached_hashes = []
        
        # 1. 批量查询缓存
        cache_tasks = []
        for image_hash in image_hashes:
            cache_key = f"recognition:{image_hash}"
            cache_tasks.append(cache_manager.get(cache_key))
        
        cached_results = await asyncio.gather(*cache_tasks)
        
        for i, image_hash in enumerate(image_hashes):
            if cached_results[i]:
                results[image_hash] = cached_results[i]
            else:
                uncached_hashes.append(image_hash)
        
        # 2. 批量查询数据库
        if uncached_hashes:
            try:
                with SessionLocal() as db:
                    # 使用IN查询批量获取
                    placeholders = ','.join([f':hash_{i}' for i in range(len(uncached_hashes))])
                    query = text(f"""
                        SELECT 
                            image_hash, result_data, confidence,
                            model_used, processing_time, created_at
                        FROM recognition_cache
                        WHERE image_hash IN ({placeholders})
                    """)
                    
                    params = {f'hash_{i}': h for i, h in enumerate(uncached_hashes)}
                    db_results = db.execute(query, params).fetchall()
                    
                    # 处理数据库结果
                    for row in db_results:
                        recognition_data = {
                            "image_hash": row.image_hash,
                            "result": json.loads(row.result_data) if row.result_data else {},
                            "confidence": row.confidence,
                            "model_used": row.model_used,
                            "processing_time": row.processing_time,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "cached": True
                        }
                        results[row.image_hash] = recognition_data
                        
                        # 异步写入缓存
                        asyncio.create_task(
                            self._cache_recognition_result(row.image_hash, recognition_data)
                        )
                        
            except Exception as e:
                logger.error(f"Batch database query failed: {e}")
        
        return results
    
    async def get_popular_recognitions(
        self,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取热门识别结果
        使用物化视图优化查询
        """
        cache_key = f"popular_recognitions:{limit}:{offset}"
        
        # 尝试缓存
        cached_result = await cache_manager.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            with SessionLocal() as db:
                query = text("""
                    SELECT 
                        rc.image_hash,
                        rc.result_data,
                        rc.confidence,
                        rc.model_used,
                        COUNT(*) as recognition_count
                    FROM recognition_cache rc
                    WHERE rc.confidence > 0.8
                    GROUP BY rc.image_hash, rc.result_data, rc.confidence, rc.model_used
                    ORDER BY recognition_count DESC, rc.confidence DESC
                    LIMIT :limit OFFSET :offset
                """)
                
                results = db.execute(query, {"limit": limit, "offset": offset}).fetchall()
                
                popular_list = []
                for row in results:
                    popular_list.append({
                        "image_hash": row.image_hash,
                        "result": json.loads(row.result_data) if row.result_data else {},
                        "confidence": row.confidence,
                        "model_used": row.model_used,
                        "recognition_count": row.recognition_count
                    })
                
                # 缓存5分钟
                await cache_manager.set(
                    cache_key, popular_list, 
                    ttl=300,
                    strategy=CacheStrategy.WRITE_THROUGH
                )
                
                return popular_list
                
        except Exception as e:
            logger.error(f"Failed to get popular recognitions: {e}")
            return []
    
    async def cleanup_old_recognitions(self, days: int = 30) -> int:
        """
        清理旧的识别记录
        保持数据库性能
        """
        try:
            with SessionLocal() as db:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                query = text("""
                    DELETE FROM recognition_cache
                    WHERE created_at < :cutoff_date
                    AND image_hash NOT IN (
                        SELECT DISTINCT image_hash 
                        FROM recognition_cache 
                        WHERE confidence > 0.9
                        GROUP BY image_hash
                        HAVING COUNT(*) > 5
                    )
                """)
                
                result = db.execute(query, {"cutoff_date": cutoff_date})
                db.commit()
                
                deleted_count = result.rowcount
                logger.info(f"Cleaned up {deleted_count} old recognition records")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0
    
    async def get_recognition_stats(self) -> Dict[str, Any]:
        """获取识别统计信息"""
        try:
            with SessionLocal() as db:
                stats_query = text("""
                    SELECT 
                        COUNT(*) as total_recognitions,
                        AVG(confidence) as avg_confidence,
                        AVG(processing_time) as avg_processing_time,
                        COUNT(DISTINCT image_hash) as unique_images,
                        COUNT(DISTINCT model_used) as models_used
                    FROM recognition_cache
                    WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
                """)
                
                result = db.execute(stats_query).fetchone()
                
                return {
                    "total_recognitions": result.total_recognitions,
                    "avg_confidence": float(result.avg_confidence) if result.avg_confidence else 0,
                    "avg_processing_time": float(result.avg_processing_time) if result.avg_processing_time else 0,
                    "unique_images": result.unique_images,
                    "models_used": result.models_used
                }
                
        except Exception as e:
            logger.error(f"Failed to get recognition stats: {e}")
            return {}

# 全局实例
recognition_repository = RecognitionRepository()