"""
测试图像处理服务

遵循TDD方法，先编写测试用例
"""

import pytest
import asyncio
import io
from pathlib import Path
from unittest.mock import Mock, patch
import base64
from PIL import Image

from app.services.image_processing.image_processor import (
    ImageProcessor, ImageFormat, ImageValidationError,
    ImageProcessingError, ProcessedImage
)


class TestImageProcessor:
    """测试图像处理器"""
    
    @pytest.fixture
    def processor(self):
        """创建图像处理器实例"""
        return ImageProcessor()
    
    @pytest.fixture
    def sample_image_bytes(self):
        """创建示例图像字节数据"""
        # 创建一个小的测试图像
        img = Image.new('RGB', (100, 100), color='red')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()
    
    @pytest.fixture
    def large_image_bytes(self):
        """创建大尺寸测试图像（但在验证限制内）"""
        img = Image.new('RGB', (2000, 2000), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()
    
    @pytest.fixture
    def oversized_image_bytes(self):
        """创建超出限制的图像"""
        img = Image.new('RGB', (3000, 3000), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()
    
    def test_processor_initialization(self, processor):
        """测试处理器初始化"""
        assert processor.max_size == 10 * 1024 * 1024  # 10MB
        assert processor.max_resolution == 2048
        assert processor.target_resolution == 1024
        assert ImageFormat.JPEG in processor.supported_formats
        assert ImageFormat.PNG in processor.supported_formats
    
    def test_validate_image_size_success(self, processor, sample_image_bytes):
        """测试图像大小验证成功"""
        # 应该不抛出异常
        processor.validate_image_size(sample_image_bytes)
    
    def test_validate_image_size_too_large(self, processor):
        """测试图像大小过大"""
        large_data = b"x" * (15 * 1024 * 1024)  # 15MB
        
        with pytest.raises(ImageValidationError) as exc_info:
            processor.validate_image_size(large_data)
        
        assert "exceeds maximum size" in str(exc_info.value)
        assert exc_info.value.error_code == "IMAGE_TOO_LARGE"
    
    def test_detect_image_format_jpeg(self, processor, sample_image_bytes):
        """测试JPEG格式检测"""
        format_detected = processor.detect_image_format(sample_image_bytes)
        assert format_detected == ImageFormat.JPEG
    
    def test_detect_image_format_png(self, processor):
        """测试PNG格式检测"""
        # 创建PNG图像
        img = Image.new('RGB', (100, 100), color='green')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        png_bytes = buf.getvalue()
        
        format_detected = processor.detect_image_format(png_bytes)
        assert format_detected == ImageFormat.PNG
    
    def test_detect_image_format_unsupported(self, processor):
        """测试不支持的格式"""
        # 创建BMP图像
        img = Image.new('RGB', (100, 100), color='yellow')
        buf = io.BytesIO()
        img.save(buf, format='BMP')
        bmp_bytes = buf.getvalue()
        
        with pytest.raises(ImageValidationError) as exc_info:
            processor.detect_image_format(bmp_bytes)
        
        assert "Unsupported image format" in str(exc_info.value)
        assert exc_info.value.error_code == "UNSUPPORTED_FORMAT"
    
    def test_get_image_dimensions(self, processor, sample_image_bytes):
        """测试获取图像尺寸"""
        width, height = processor.get_image_dimensions(sample_image_bytes)
        assert width == 100
        assert height == 100
    
    def test_validate_image_dimensions_success(self, processor, sample_image_bytes):
        """测试图像尺寸验证成功"""
        # 应该不抛出异常
        processor.validate_image_dimensions(sample_image_bytes)
    
    def test_validate_image_dimensions_too_large(self, processor, oversized_image_bytes):
        """测试图像尺寸过大"""
        with pytest.raises(ImageValidationError) as exc_info:
            processor.validate_image_dimensions(oversized_image_bytes)
        
        assert "exceeds maximum resolution" in str(exc_info.value)
        assert exc_info.value.error_code == "RESOLUTION_TOO_HIGH"
    
    def test_resize_image_no_resize_needed(self, processor, sample_image_bytes):
        """测试不需要调整大小的图像"""
        resized = processor.resize_image(sample_image_bytes, target_size=1024)
        
        # 图像已经小于目标尺寸，应该返回原图
        assert len(resized) <= len(sample_image_bytes) * 1.1  # 允许一些压缩差异
    
    def test_resize_image_needs_resize(self, processor, large_image_bytes):
        """测试需要调整大小的图像"""
        resized = processor.resize_image(large_image_bytes, target_size=1024)
        
        # 检查调整后的尺寸
        img = Image.open(io.BytesIO(resized))
        assert max(img.width, img.height) <= 1024
        assert len(resized) < len(large_image_bytes)  # 应该更小
    
    def test_optimize_image_quality(self, processor, sample_image_bytes):
        """测试图像质量优化"""
        optimized = processor.optimize_image_quality(sample_image_bytes, quality=85)
        
        # 检查优化后的图像仍然有效
        img = Image.open(io.BytesIO(optimized))
        assert img.format == 'JPEG'
        assert img.size == (100, 100)
    
    def test_convert_to_base64(self, processor, sample_image_bytes):
        """测试Base64编码"""
        base64_str = processor.convert_to_base64(sample_image_bytes)
        
        assert isinstance(base64_str, str)
        assert len(base64_str) > 0
        
        # 验证可以解码回原数据
        decoded = base64.b64decode(base64_str)
        assert decoded == sample_image_bytes
    
    def test_convert_from_base64(self, processor, sample_image_bytes):
        """测试Base64解码"""
        base64_str = base64.b64encode(sample_image_bytes).decode('utf-8')
        decoded = processor.convert_from_base64(base64_str)
        
        assert decoded == sample_image_bytes
    
    def test_convert_from_base64_invalid(self, processor):
        """测试无效Base64解码"""
        with pytest.raises(ImageValidationError) as exc_info:
            processor.convert_from_base64("invalid-base64-string!")
        
        assert "Invalid base64 encoding" in str(exc_info.value)
        assert exc_info.value.error_code == "INVALID_BASE64"
    
    @pytest.mark.asyncio
    async def test_process_image_complete_pipeline(self, processor, large_image_bytes):
        """测试完整的图像处理流程"""
        processed = await processor.process_image(
            image_data=large_image_bytes,
            target_resolution=1024,
            quality=85,
            format_output=ImageFormat.JPEG
        )
        
        assert isinstance(processed, ProcessedImage)
        assert processed.format == ImageFormat.JPEG
        assert processed.width <= 1024
        assert processed.height <= 1024
        assert processed.size_bytes < len(large_image_bytes)
        assert processed.base64_data is not None
        assert processed.compression_ratio > 0
    
    @pytest.mark.asyncio
    async def test_process_image_with_validation_error(self, processor):
        """测试图像处理验证错误"""
        # 使用无效图像数据
        invalid_data = b"not-an-image"
        
        with pytest.raises(ImageValidationError):
            await processor.process_image(invalid_data)
    
    @pytest.mark.asyncio
    async def test_process_image_from_base64(self, processor, sample_image_bytes):
        """测试从Base64处理图像"""
        base64_str = base64.b64encode(sample_image_bytes).decode('utf-8')
        
        processed = await processor.process_from_base64(
            base64_data=base64_str,
            target_resolution=512,
            quality=90
        )
        
        assert isinstance(processed, ProcessedImage)
        assert processed.format in [ImageFormat.JPEG, ImageFormat.PNG]
        assert processed.base64_data is not None
    
    def test_create_thumbnail(self, processor, sample_image_bytes):
        """测试创建缩略图"""
        thumbnail = processor.create_thumbnail(sample_image_bytes, size=64)
        
        img = Image.open(io.BytesIO(thumbnail))
        assert max(img.width, img.height) <= 64
        assert len(thumbnail) < len(sample_image_bytes)
    
    def test_extract_metadata(self, processor, sample_image_bytes):
        """测试提取图像元数据"""
        metadata = processor.extract_metadata(sample_image_bytes)
        
        assert 'format' in metadata
        assert 'width' in metadata
        assert 'height' in metadata
        assert 'size_bytes' in metadata
        assert metadata['format'] == 'JPEG'
        assert metadata['width'] == 100
        assert metadata['height'] == 100
    
    def test_validate_aspect_ratio(self, processor):
        """测试纵横比验证"""
        # 创建极端纵横比的图像
        tall_img = Image.new('RGB', (100, 2000), color='red')
        buf = io.BytesIO()
        tall_img.save(buf, format='JPEG')
        tall_bytes = buf.getvalue()
        
        with pytest.raises(ImageValidationError) as exc_info:
            processor.validate_aspect_ratio(tall_bytes, max_ratio=5.0)
        
        assert "Invalid aspect ratio" in str(exc_info.value)
        assert exc_info.value.error_code == "INVALID_ASPECT_RATIO"
    
    def test_batch_process_images(self, processor, sample_image_bytes):
        """测试批量图像处理"""
        images = [sample_image_bytes, sample_image_bytes, sample_image_bytes]
        
        async def run_batch():
            results = await processor.batch_process_images(
                images, 
                target_resolution=512,
                quality=80
            )
            return results
        
        results = asyncio.run(run_batch())
        
        assert len(results) == 3
        for result in results:
            assert isinstance(result, ProcessedImage)
            assert result.width <= 512
            assert result.height <= 512


class TestImageFormat:
    """测试图像格式枚举"""
    
    def test_image_format_values(self):
        """测试图像格式值"""
        assert ImageFormat.JPEG.value == "jpeg"
        assert ImageFormat.PNG.value == "png"
        assert ImageFormat.WEBP.value == "webp"
    
    def test_image_format_from_string(self):
        """测试从字符串创建格式"""
        assert ImageFormat.from_string("jpeg") == ImageFormat.JPEG
        assert ImageFormat.from_string("JPEG") == ImageFormat.JPEG
        assert ImageFormat.from_string("png") == ImageFormat.PNG
        
        with pytest.raises(ValueError):
            ImageFormat.from_string("bmp")


class TestProcessedImage:
    """测试处理后图像数据类"""
    
    def test_processed_image_creation(self):
        """测试处理后图像创建"""
        processed = ProcessedImage(
            data=b"test_data",
            format=ImageFormat.JPEG,
            width=1024,
            height=768,
            size_bytes=1000,
            base64_data="dGVzdF9kYXRh",
            compression_ratio=0.7
        )
        
        assert processed.data == b"test_data"
        assert processed.format == ImageFormat.JPEG
        assert processed.width == 1024
        assert processed.height == 768
        assert processed.size_bytes == 1000
        assert processed.compression_ratio == 0.7
    
    def test_processed_image_aspect_ratio(self):
        """测试纵横比计算"""
        processed = ProcessedImage(
            data=b"test",
            format=ImageFormat.JPEG,
            width=1024,
            height=768,
            size_bytes=1000,
            base64_data="dGVzdA==",
            compression_ratio=0.8
        )
        
        assert abs(processed.aspect_ratio - (1024/768)) < 0.001


class TestImageValidationError:
    """测试图像验证错误"""
    
    def test_image_validation_error_creation(self):
        """测试图像验证错误创建"""
        error = ImageValidationError(
            message="Test error",
            error_code="TEST_ERROR",
            details={"key": "value"}
        )
        
        assert str(error) == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.details == {"key": "value"}


class TestImageProcessingError:
    """测试图像处理错误"""
    
    def test_image_processing_error_creation(self):
        """测试图像处理错误创建"""
        error = ImageProcessingError(
            message="Processing failed",
            error_code="PROCESSING_FAILED",
            details={"operation": "resize"}
        )
        
        assert str(error) == "Processing failed"
        assert error.error_code == "PROCESSING_FAILED"
        assert error.details == {"operation": "resize"}