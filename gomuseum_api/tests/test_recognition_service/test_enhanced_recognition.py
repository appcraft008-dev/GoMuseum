"""
测试升级后的识别服务
集成AI适配器、图像处理和监控功能
"""

import pytest
import asyncio
import io
import hashlib
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from PIL import Image

from app.services.recognition_service import RecognitionService
from app.services.ai_service.enhanced_model_selector import EnhancedModelSelector
from app.services.image_processing.image_processor import ImageProcessor, ProcessedImage, ImageFormat
from app.services.ai_service.monitoring import AIServiceMonitor
from app.services.ai_service.config import ModelConfig


class TestEnhancedRecognitionService:
    """测试增强的识别服务"""
    
    @pytest.fixture
    def sample_image_bytes(self):
        """创建示例图像字节数据"""
        img = Image.new('RGB', (100, 100), color='red')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()
    
    @pytest.fixture
    def large_image_bytes(self):
        """创建大尺寸图像"""
        img = Image.new('RGB', (2000, 2000), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()
    
    @pytest.fixture
    def image_hash(self, sample_image_bytes):
        """生成图像哈希"""
        return hashlib.md5(sample_image_bytes).hexdigest()
    
    @pytest.fixture
    def mock_model_selector(self):
        """模拟模型选择器"""
        selector = Mock(spec=EnhancedModelSelector)
        selector.select_best_model = AsyncMock(return_value=Mock(
            model_name="gpt-4-vision-preview",
            provider="openai",
            max_tokens=1024,
            temperature=0.1
        ))
        return selector
    
    @pytest.fixture
    def mock_image_processor(self):
        """模拟图像处理器"""
        processor = Mock(spec=ImageProcessor)
        processor.process_image = AsyncMock(return_value=ProcessedImage(
            data=b"processed_image_data",
            format=ImageFormat.JPEG,
            width=1024,
            height=1024,
            size_bytes=50000,
            base64_data="dGVzdF9pbWFnZV9kYXRh",
            compression_ratio=0.7
        ))
        return processor
    
    @pytest.fixture
    def mock_ai_monitor(self):
        """模拟AI监控器"""
        monitor = Mock(spec=AIServiceMonitor)
        monitor.record_request_start = Mock()
        monitor.record_request_end = Mock()
        monitor.record_error = Mock()
        return monitor
    
    @pytest.fixture
    def mock_ai_adapter(self):
        """模拟AI适配器"""
        adapter = AsyncMock()
        adapter.recognize_artwork = AsyncMock(return_value={
            "success": True,
            "confidence": 0.85,
            "description": "This is the famous Mona Lisa painting",
            "candidates": [
                {
                    "artwork_id": "mona-lisa-001",
                    "name": "Mona Lisa",
                    "artist": "Leonardo da Vinci",
                    "confidence": 0.85,
                    "museum": "Louvre Museum",
                    "period": "1503-1519"
                }
            ],
            "cost_usd": 0.01,
            "model_used": "gpt-4-vision-preview"
        })
        adapter.health_check = AsyncMock(return_value=True)
        return adapter
    
    @pytest.fixture
    def enhanced_recognition_service(self, mock_model_selector, 
                                          mock_image_processor, mock_ai_monitor):
        """创建增强的识别服务实例"""
        # 直接创建服务实例并模拟依赖
        service = RecognitionService.__new__(RecognitionService)
        service.cache_ttl = 3600
        service.confidence_threshold = 0.7
        
        # 注入模拟依赖
        service.image_processor = mock_image_processor
        service.model_selector = mock_model_selector
        service.ai_monitor = mock_ai_monitor
        service._adapters = {}
        
        return service
    
    def test_enhanced_recognition_service_initialization(self, enhanced_recognition_service):
        """测试增强识别服务初始化"""
        service = enhanced_recognition_service
        
        assert hasattr(service, 'model_selector')
        assert hasattr(service, 'image_processor')
        assert hasattr(service, 'ai_monitor')
        assert hasattr(service, '_adapters')
    
    @pytest.mark.asyncio
    async def test_recognize_image_with_ai_integration(self, enhanced_recognition_service,
                                                     mock_ai_adapter, sample_image_bytes, 
                                                     image_hash):
        """测试集成AI的图像识别"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        result = await service.recognize_image_enhanced(
            image_bytes=sample_image_bytes,
            image_hash=image_hash,
            language="en"
        )
        
        assert result["success"] is True
        assert result["confidence"] == 0.85
        assert "processing_time" in result
        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["name"] == "Mona Lisa"
        assert result["image_hash"] == image_hash
        assert "model_used" in result
        assert result["cached"] is False
        
        # 验证监控调用
        service.ai_monitor.record_request_start.assert_called_once()
        service.ai_monitor.record_request_end.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_recognize_image_with_preprocessing(self, enhanced_recognition_service,
                                                    mock_ai_adapter, large_image_bytes):
        """测试图像预处理流程"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        image_hash = hashlib.md5(large_image_bytes).hexdigest()
        
        result = await service.recognize_image_enhanced(
            image_bytes=large_image_bytes,
            image_hash=image_hash
        )
        
        # 验证图像处理器被调用
        service.image_processor.process_image.assert_called_once()
        
        # 验证使用处理后的图像调用AI适配器
        mock_ai_adapter.recognize_artwork.assert_called_once()
        call_args = mock_ai_adapter.recognize_artwork.call_args
        assert "image_data" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_recognize_image_model_selection(self, enhanced_recognition_service,
                                                  mock_ai_adapter, sample_image_bytes,
                                                  image_hash):
        """测试模型选择逻辑"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        await service.recognize_image_enhanced(
            image_bytes=sample_image_bytes,
            image_hash=image_hash,
            strategy="accuracy"
        )
        
        # 验证模型选择器被调用
        service.model_selector.select_best_model.assert_called_once_with(
            strategy="accuracy",
            constraints=None
        )
    
    @pytest.mark.asyncio
    async def test_recognize_image_error_handling(self, enhanced_recognition_service,
                                                 mock_ai_adapter, sample_image_bytes,
                                                 image_hash):
        """测试错误处理"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        # 模拟AI适配器错误
        mock_ai_adapter.recognize_artwork.side_effect = Exception("API Error")
        
        result = await service.recognize_image_enhanced(
            image_bytes=sample_image_bytes,
            image_hash=image_hash
        )
        
        assert result["success"] is False
        assert "error" in result
        assert result["confidence"] == 0.0
        assert len(result["candidates"]) == 0
        
        # 验证错误监控
        service.ai_monitor.record_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_recognize_image_fallback_model(self, enhanced_recognition_service,
                                                 sample_image_bytes, image_hash):
        """测试模型回退机制"""
        service = enhanced_recognition_service
        
        # 模拟主模型失败，回退模型成功
        primary_adapter = AsyncMock()
        primary_adapter.recognize_artwork.side_effect = Exception("Primary model failed")
        
        fallback_adapter = AsyncMock()
        fallback_adapter.recognize_artwork.return_value = {
            "success": True,
            "confidence": 0.75,
            "description": "Fallback recognition result",
            "candidates": [{"name": "Fallback Artwork"}],
            "cost_usd": 0.005,
            "model_used": "fallback-model"
        }
        
        service._adapters = {
            "openai": primary_adapter,
            "fallback": fallback_adapter
        }
        
        # 模拟模型选择器返回回退列表
        service.model_selector.select_best_model.side_effect = [
            Mock(model_name="gpt-4-vision", provider="openai"),
            Mock(model_name="fallback-model", provider="fallback")
        ]
        
        result = await service.recognize_image_enhanced(
            image_bytes=sample_image_bytes,
            image_hash=image_hash,
            enable_fallback=True
        )
        
        assert result["success"] is True
        assert result["model_used"] == "fallback-model"
    
    @pytest.mark.asyncio
    async def test_recognize_image_caching_integration(self, enhanced_recognition_service,
                                                      mock_ai_adapter, sample_image_bytes,
                                                      image_hash):
        """测试缓存集成"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        # Mock缓存方法
        service.get_cached_result = AsyncMock(return_value=None)
        service.cache_result = AsyncMock(return_value=True)
        
        result = await service.recognize_image_enhanced(
            image_bytes=sample_image_bytes,
            image_hash=image_hash
        )
        
        # 验证缓存查询和存储
        service.get_cached_result.assert_called_once_with(image_hash)
        service.cache_result.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_recognize_image_cost_tracking(self, enhanced_recognition_service,
                                               mock_ai_adapter, sample_image_bytes,
                                               image_hash):
        """测试成本跟踪"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        result = await service.recognize_image_enhanced(
            image_bytes=sample_image_bytes,
            image_hash=image_hash
        )
        
        assert "cost_usd" in result
        assert isinstance(result["cost_usd"], float)
        assert result["cost_usd"] >= 0
    
    @pytest.mark.asyncio
    async def test_recognize_image_language_support(self, enhanced_recognition_service,
                                                   mock_ai_adapter, sample_image_bytes,
                                                   image_hash):
        """测试多语言支持"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        # 测试中文响应
        mock_ai_adapter.recognize_artwork.return_value["candidates"][0].update({
            "name": "蒙娜丽莎",
            "artist": "列奥纳多·达芬奇",
            "museum": "卢浮宫"
        })
        
        result = await service.recognize_image_enhanced(
            image_bytes=sample_image_bytes,
            image_hash=image_hash,
            language="zh"
        )
        
        # 验证语言参数传递
        call_args = mock_ai_adapter.recognize_artwork.call_args[1]
        assert call_args["language"] == "zh"
    
    @pytest.mark.asyncio
    async def test_batch_recognition(self, enhanced_recognition_service, mock_ai_adapter):
        """测试批量识别"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        # 创建多个图像
        images = []
        for i in range(3):
            img = Image.new('RGB', (100, 100), color='red')
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            images.append(buf.getvalue())
        
        results = await service.batch_recognize_images(images)
        
        assert len(results) == 3
        for result in results:
            assert "success" in result
            assert "candidates" in result
            assert "processing_time" in result
    
    def test_adapter_registration(self, enhanced_recognition_service):
        """测试适配器注册"""
        service = enhanced_recognition_service
        
        mock_adapter = Mock()
        service.register_adapter("test_provider", mock_adapter)
        
        assert "test_provider" in service._adapters
        assert service._adapters["test_provider"] == mock_adapter
    
    @pytest.mark.asyncio
    async def test_health_check_integration(self, enhanced_recognition_service, mock_ai_adapter):
        """测试健康检查集成"""
        service = enhanced_recognition_service
        service._adapters = {"openai": mock_ai_adapter}
        
        health_status = await service.get_enhanced_health_status()
        
        assert "adapters" in health_status
        assert "image_processor" in health_status
        assert "model_selector" in health_status
        assert "monitoring" in health_status
        
        # 验证适配器健康检查
        mock_ai_adapter.health_check.assert_called_once()


class TestEnhancedRecognitionServiceIntegration:
    """测试增强识别服务集成场景"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_recognition_flow(self):
        """测试端到端识别流程"""
        # 这个测试需要真实的依赖注入
        # 在实际实现中会包含完整的集成测试
        pass
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """测试负载下的性能"""
        # 性能测试用例
        pass
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """测试并发请求处理"""
        # 并发测试用例
        pass