"""
图像处理服务

提供图像验证、格式转换、尺寸调整、质量优化等功能
"""

import asyncio
import base64
import io
import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from PIL import Image, ImageOps
import pillow_heif

# 注册HEIF格式支持
pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)


class ImageFormat(Enum):
    """支持的图像格式"""
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"
    HEIC = "heic"
    
    @classmethod
    def from_string(cls, format_str: str) -> 'ImageFormat':
        """从字符串创建格式枚举"""
        format_str = format_str.lower()
        for fmt in cls:
            if fmt.value == format_str:
                return fmt
        raise ValueError(f"Unsupported format: {format_str}")


@dataclass
class ProcessedImage:
    """处理后的图像数据"""
    data: bytes
    format: ImageFormat
    width: int
    height: int
    size_bytes: int
    base64_data: str
    compression_ratio: float
    
    @property
    def aspect_ratio(self) -> float:
        """计算纵横比"""
        return self.width / self.height if self.height > 0 else 0.0


class ImageValidationError(Exception):
    """图像验证错误"""
    
    def __init__(self, message: str, error_code: str, details: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class ImageProcessingError(Exception):
    """图像处理错误"""
    
    def __init__(self, message: str, error_code: str, details: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class ImageProcessor:
    """图像处理器"""
    
    def __init__(self, 
                 max_size: int = None,
                 max_resolution: int = None,
                 target_resolution: int = None):
        # 从配置文件获取参数，避免魔数
        from app.core.config import settings
        self.max_size = max_size or getattr(settings, 'max_image_size', 10 * 1024 * 1024)  # 10MB
        self.max_resolution = max_resolution or getattr(settings, 'max_image_resolution', 2048)
        self.target_resolution = target_resolution or getattr(settings, 'target_image_resolution', 1024)
        self.supported_formats = {
            ImageFormat.JPEG,
            ImageFormat.PNG,
            ImageFormat.WEBP,
            ImageFormat.HEIC
        }
        
        logger.info(f"ImageProcessor initialized: max_size={max_size}, "
                   f"max_resolution={max_resolution}, target_resolution={target_resolution}")
    
    def validate_image_size(self, image_data: bytes) -> None:
        """验证图像文件大小"""
        if len(image_data) > self.max_size:
            raise ImageValidationError(
                f"Image size {len(image_data)} bytes exceeds maximum size {self.max_size} bytes",
                error_code="IMAGE_TOO_LARGE",
                details={"size": len(image_data), "max_size": self.max_size}
            )
    
    def detect_image_format(self, image_data: bytes) -> ImageFormat:
        """检测图像格式"""
        try:
            img = Image.open(io.BytesIO(image_data))
            format_str = img.format.lower()
            
            if format_str == 'jpeg':
                return ImageFormat.JPEG
            elif format_str == 'png':
                return ImageFormat.PNG
            elif format_str == 'webp':
                return ImageFormat.WEBP
            elif format_str == 'heif':
                return ImageFormat.HEIC
            else:
                raise ImageValidationError(
                    f"Unsupported image format: {format_str}",
                    error_code="UNSUPPORTED_FORMAT",
                    details={"detected_format": format_str}
                )
                
        except Exception as e:
            if isinstance(e, ImageValidationError):
                raise
            raise ImageValidationError(
                f"Failed to detect image format: {str(e)}",
                error_code="FORMAT_DETECTION_FAILED",
                details={"error": str(e)}
            )
    
    def get_image_dimensions(self, image_data: bytes) -> Tuple[int, int]:
        """获取图像尺寸"""
        try:
            img = Image.open(io.BytesIO(image_data))
            return img.width, img.height
        except Exception as e:
            raise ImageValidationError(
                f"Failed to get image dimensions: {str(e)}",
                error_code="DIMENSION_READ_FAILED",
                details={"error": str(e)}
            )
    
    def validate_image_dimensions(self, image_data: bytes) -> None:
        """验证图像尺寸"""
        width, height = self.get_image_dimensions(image_data)
        
        if width > self.max_resolution or height > self.max_resolution:
            raise ImageValidationError(
                f"Image resolution {width}x{height} exceeds maximum resolution {self.max_resolution}",
                error_code="RESOLUTION_TOO_HIGH",
                details={
                    "width": width,
                    "height": height,
                    "max_resolution": self.max_resolution
                }
            )
    
    def validate_aspect_ratio(self, image_data: bytes, max_ratio: float = 10.0) -> None:
        """验证图像纵横比"""
        width, height = self.get_image_dimensions(image_data)
        
        aspect_ratio = max(width, height) / min(width, height)
        
        if aspect_ratio > max_ratio:
            raise ImageValidationError(
                f"Invalid aspect ratio {aspect_ratio:.2f}, maximum allowed is {max_ratio}",
                error_code="INVALID_ASPECT_RATIO",
                details={
                    "aspect_ratio": aspect_ratio,
                    "max_ratio": max_ratio,
                    "width": width,
                    "height": height
                }
            )
    
    def resize_image(self, image_data: bytes, target_size: int) -> bytes:
        """调整图像大小"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            # 如果图像已经小于目标尺寸，则不需要调整
            if max(img.width, img.height) <= target_size:
                # 仍然重新编码以优化
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=95, optimize=True)
                return output.getvalue()
            
            # 计算新尺寸，保持纵横比
            if img.width > img.height:
                new_width = target_size
                new_height = int((target_size * img.height) / img.width)
            else:
                new_height = target_size
                new_width = int((target_size * img.width) / img.height)
            
            # 使用高质量重采样
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 保存到字节流
            output = io.BytesIO()
            if img.mode in ('RGBA', 'LA', 'P'):
                # 处理透明通道
                resized_img = resized_img.convert('RGB')
            
            resized_img.save(output, format='JPEG', quality=95, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to resize image: {str(e)}",
                error_code="RESIZE_FAILED",
                details={"error": str(e), "target_size": target_size}
            )
    
    def optimize_image_quality(self, image_data: bytes, quality: int = 85) -> bytes:
        """优化图像质量"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            # 自动方向校正
            img = ImageOps.exif_transpose(img)
            
            # 转换为RGB如果需要
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to optimize image quality: {str(e)}",
                error_code="QUALITY_OPTIMIZATION_FAILED",
                details={"error": str(e), "quality": quality}
            )
    
    def convert_to_base64(self, image_data: bytes) -> str:
        """转换为Base64编码"""
        try:
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to convert to base64: {str(e)}",
                error_code="BASE64_ENCODING_FAILED",
                details={"error": str(e)}
            )
    
    def convert_from_base64(self, base64_str: str) -> bytes:
        """从Base64解码"""
        try:
            return base64.b64decode(base64_str)
        except Exception as e:
            raise ImageValidationError(
                f"Invalid base64 encoding: {str(e)}",
                error_code="INVALID_BASE64",
                details={"error": str(e)}
            )
    
    def create_thumbnail(self, image_data: bytes, size: int = 128) -> bytes:
        """创建缩略图"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            # 创建缩略图，保持纵横比
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # 转换为RGB
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=80, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to create thumbnail: {str(e)}",
                error_code="THUMBNAIL_CREATION_FAILED",
                details={"error": str(e), "size": size}
            )
    
    def extract_metadata(self, image_data: bytes) -> Dict[str, Any]:
        """提取图像元数据"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            metadata = {
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "size_bytes": len(image_data),
                "aspect_ratio": img.width / img.height if img.height > 0 else 0
            }
            
            # 提取EXIF数据（如果有）
            if hasattr(img, '_getexif') and img._getexif():
                exif = img._getexif()
                if exif:
                    metadata["has_exif"] = True
                    # 提取一些关键EXIF信息
                    orientation = exif.get(274)  # Orientation tag
                    if orientation:
                        metadata["orientation"] = orientation
            else:
                metadata["has_exif"] = False
            
            return metadata
            
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to extract metadata: {str(e)}",
                error_code="METADATA_EXTRACTION_FAILED",
                details={"error": str(e)}
            )
    
    async def process_image(self, 
                          image_data: bytes,
                          target_resolution: int = None,
                          quality: int = 85,
                          format_output: ImageFormat = ImageFormat.JPEG) -> ProcessedImage:
        """完整的图像处理流程"""
        try:
            # 1. 验证图像大小
            self.validate_image_size(image_data)
            
            # 2. 检测并验证格式
            detected_format = self.detect_image_format(image_data)
            
            # 3. 验证尺寸
            self.validate_image_dimensions(image_data)
            
            # 4. 验证纵横比
            self.validate_aspect_ratio(image_data)
            
            # 5. 获取原始尺寸
            orig_width, orig_height = self.get_image_dimensions(image_data)
            original_size = len(image_data)
            
            # 6. 调整大小（如果需要）
            target_res = target_resolution or self.target_resolution
            processed_data = self.resize_image(image_data, target_res)
            
            # 7. 优化质量
            processed_data = self.optimize_image_quality(processed_data, quality)
            
            # 8. 获取最终尺寸
            final_width, final_height = self.get_image_dimensions(processed_data)
            final_size = len(processed_data)
            
            # 9. 转换为Base64
            base64_data = self.convert_to_base64(processed_data)
            
            # 10. 计算压缩比
            compression_ratio = final_size / original_size if original_size > 0 else 1.0
            
            result = ProcessedImage(
                data=processed_data,
                format=format_output,
                width=final_width,
                height=final_height,
                size_bytes=final_size,
                base64_data=base64_data,
                compression_ratio=compression_ratio
            )
            
            logger.info(f"Image processed successfully: {orig_width}x{orig_height} -> "
                       f"{final_width}x{final_height}, compression: {compression_ratio:.2f}")
            
            return result
            
        except (ImageValidationError, ImageProcessingError):
            raise
        except Exception as e:
            raise ImageProcessingError(
                f"Unexpected error during image processing: {str(e)}",
                error_code="PROCESSING_FAILED",
                details={"error": str(e)}
            )
    
    async def process_from_base64(self, 
                                base64_data: str,
                                target_resolution: int = None,
                                quality: int = 85,
                                format_output: ImageFormat = ImageFormat.JPEG) -> ProcessedImage:
        """从Base64数据处理图像"""
        try:
            # 解码Base64
            image_data = self.convert_from_base64(base64_data)
            
            # 处理图像
            return await self.process_image(
                image_data=image_data,
                target_resolution=target_resolution,
                quality=quality,
                format_output=format_output
            )
            
        except (ImageValidationError, ImageProcessingError):
            raise
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to process image from base64: {str(e)}",
                error_code="BASE64_PROCESSING_FAILED",
                details={"error": str(e)}
            )
    
    async def batch_process_images(self, 
                                 images: List[bytes],
                                 target_resolution: int = None,
                                 quality: int = 85,
                                 format_output: ImageFormat = ImageFormat.JPEG) -> List[ProcessedImage]:
        """批量处理图像"""
        tasks = []
        
        for image_data in images:
            task = self.process_image(
                image_data=image_data,
                target_resolution=target_resolution,
                quality=quality,
                format_output=format_output
            )
            tasks.append(task)
        
        # 并发处理
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果，保留异常信息
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process image {i}: {result}")
                # 可以选择跳过失败的图像或包含错误信息
                continue
            processed_results.append(result)
        
        return processed_results