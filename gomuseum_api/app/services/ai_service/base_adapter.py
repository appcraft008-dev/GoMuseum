"""
Vision Model Adapter Base Class

提供统一的AI视觉模型接口，支持多个Provider的动态切换
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class VisionModelAdapter(ABC):
    """
    AI视觉模型适配器抽象基类
    
    所有AI模型适配器都必须继承此类并实现抽象方法。
    这确保了统一的接口和一致的行为。
    """
    
    # 子类必须定义这些属性
    model_name: str = "unknown"
    provider_name: str = "unknown"
    max_image_size: int = 10 * 1024 * 1024  # 10MB default
    supported_formats: List[str] = ["jpeg", "jpg", "png", "gif", "webp"]
    
    def __init__(self, **kwargs):
        """初始化适配器"""
        self._config = kwargs
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_cost": 0.0,
            "average_response_time": 0.0
        }
    
    @abstractmethod
    async def recognize_artwork(
        self, 
        image_bytes: bytes, 
        language: str = "zh", 
        **kwargs
    ) -> Dict[str, Any]:
        """
        识别艺术品
        
        Args:
            image_bytes: 图像二进制数据
            language: 语言代码 (zh, en, fr, de, es, it)
            **kwargs: 其他参数
            
        Returns:
            Dict包含识别结果:
            {
                "success": bool,
                "candidates": [
                    {
                        "artwork_id": str,
                        "name": str,
                        "artist": str,
                        "confidence": float,
                        "period": str,
                        "museum_section": str,
                        "visual_features": List[str]
                    }
                ],
                "processing_time": float,
                "model_used": str,
                "timestamp": str
            }
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            bool: True if model is available and healthy
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            Dict包含模型信息:
            {
                "model_name": str,
                "provider": str,
                "version": str,
                "capabilities": List[str],
                "pricing": Dict[str, float]
            }
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, image_bytes: bytes) -> float:
        """
        估算调用成本
        
        Args:
            image_bytes: 图像数据
            
        Returns:
            float: 预估成本（美元）
        """
        pass
    
    # 以下是具体实现的方法，子类可以选择性重写
    
    def get_accuracy_score(self) -> float:
        """
        获取模型准确率评分
        
        Returns:
            float: 0.0-1.0之间的准确率评分
        """
        # 默认返回基础分数，子类应该重写此方法
        return 0.8
    
    def get_average_response_time(self) -> float:
        """
        获取平均响应时间
        
        Returns:
            float: 平均响应时间（秒）
        """
        return self._stats.get("average_response_time", 3.0)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取适配器统计信息
        
        Returns:
            Dict: 统计信息
        """
        return {
            **self._stats,
            "model_name": self.model_name,
            "provider_name": self.provider_name,
            "success_rate": (
                self._stats["successful_requests"] / max(1, self._stats["total_requests"])
            )
        }
    
    def _update_stats(
        self, 
        success: bool, 
        cost: float = 0.0, 
        response_time: float = 0.0
    ):
        """
        更新统计信息
        
        Args:
            success: 请求是否成功
            cost: 请求成本
            response_time: 响应时间
        """
        self._stats["total_requests"] += 1
        
        if success:
            self._stats["successful_requests"] += 1
        else:
            self._stats["failed_requests"] += 1
        
        self._stats["total_cost"] += cost
        
        # 计算移动平均响应时间
        if response_time > 0:
            current_avg = self._stats["average_response_time"]
            total_requests = self._stats["total_requests"]
            
            # 使用移动平均算法
            if total_requests == 1:
                self._stats["average_response_time"] = response_time
            else:
                weight = min(0.1, 1.0 / total_requests)  # 权重衰减
                self._stats["average_response_time"] = (
                    current_avg * (1 - weight) + response_time * weight
                )
    
    def _validate_image(self, image_bytes: bytes) -> bool:
        """
        验证图像数据
        
        Args:
            image_bytes: 图像二进制数据
            
        Returns:
            bool: True if valid
            
        Raises:
            ImageTooLargeError: 图像过大
            InvalidImageFormatError: 无效格式
        """
        from .exceptions import ImageTooLargeError, InvalidImageFormatError
        
        # 检查文件大小
        if len(image_bytes) > self.max_image_size:
            raise ImageTooLargeError(len(image_bytes), self.max_image_size)
        
        # 检查图像格式
        if not self._is_valid_image_format(image_bytes):
            raise InvalidImageFormatError(
                format_detected=self._detect_image_format(image_bytes),
                supported_formats=self.supported_formats
            )
        
        return True
    
    def _is_valid_image_format(self, image_bytes: bytes) -> bool:
        """检查图像格式是否支持"""
        if not image_bytes or len(image_bytes) < 10:
            return False
        
        # 检查常见图像格式的文件头
        format_signatures = {
            b'\xff\xd8\xff': 'jpeg',  # JPEG
            b'\x89PNG\r\n\x1a\n': 'png',  # PNG
            b'GIF87a': 'gif',  # GIF87a
            b'GIF89a': 'gif',  # GIF89a
            b'RIFF': 'webp',  # WebP (需要进一步检查)
            b'\x00\x00\x01\x00': 'ico',  # ICO
            b'BM': 'bmp'  # BMP
        }
        
        for signature, format_name in format_signatures.items():
            if image_bytes.startswith(signature):
                # 对于WebP，需要额外检查
                if format_name == 'webp':
                    if len(image_bytes) >= 12 and image_bytes[8:12] == b'WEBP':
                        return 'webp' in [f.lower() for f in self.supported_formats]
                return format_name in [f.lower() for f in self.supported_formats]
        
        return False
    
    def _detect_image_format(self, image_bytes: bytes) -> Optional[str]:
        """检测图像格式"""
        if not image_bytes or len(image_bytes) < 10:
            return None
        
        if image_bytes.startswith(b'\xff\xd8\xff'):
            return 'jpeg'
        elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        elif image_bytes.startswith((b'GIF87a', b'GIF89a')):
            return 'gif'
        elif image_bytes.startswith(b'RIFF') and len(image_bytes) >= 12:
            if image_bytes[8:12] == b'WEBP':
                return 'webp'
        elif image_bytes.startswith(b'BM'):
            return 'bmp'
        elif image_bytes.startswith(b'\x00\x00\x01\x00'):
            return 'ico'
        
        return 'unknown'
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        # 子类可以重写此方法来清理资源
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name}, provider={self.provider_name})"