"""
Image Service
Handles image validation, preprocessing, and encoding
"""

import hashlib
import base64
from PIL import Image
from io import BytesIO
from app.core.exceptions import ValidationException, ImageProcessingException
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class ImageService:
    """Service for image processing and validation"""

    MAX_SIZE_MB = settings.MAX_IMAGE_SIZE_MB
    ALLOWED_FORMATS = settings.ALLOWED_IMAGE_FORMATS
    COMPRESSION_QUALITY = settings.IMAGE_COMPRESSION_QUALITY
    MAX_WIDTH = settings.MAX_IMAGE_WIDTH

    # Magic bytes for image format detection
    JPEG_MAGIC_BYTES = [
        bytes([0xFF, 0xD8, 0xFF]),  # JPEG
    ]
    PNG_MAGIC_BYTES = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])  # PNG

    @staticmethod
    def validate_image(image_data: bytes) -> bool:
        """
        Validate image format and size

        Args:
            image_data: Raw image bytes

        Returns:
            True if valid

        Raises:
            ValidationException: If validation fails
        """
        # 1. Check file size
        if len(image_data) > ImageService.MAX_SIZE_MB * 1024 * 1024:
            raise ValidationException(
                f"Image size exceeds {ImageService.MAX_SIZE_MB}MB",
                detail=f"Received {len(image_data) / (1024 * 1024):.2f}MB",
            )

        # 2. Check for empty data
        if len(image_data) == 0:
            raise ValidationException("Image data is empty")

        # 3. Validate image format using PIL
        try:
            img = Image.open(BytesIO(image_data))
            if img.format not in ImageService.ALLOWED_FORMATS:
                raise ValidationException(
                    f"Image format {img.format} not supported",
                    detail=(
                        f"Allowed formats: {', '.join(ImageService.ALLOWED_FORMATS)}"
                    ),
                )

            # Verify the image can be loaded (not corrupted)
            img.verify()

            return True

        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                "Invalid image file", detail=f"Failed to parse image: {str(e)}"
            )

    @staticmethod
    def generate_hash(image_data: bytes) -> str:
        """
        Generate SHA256 hash of image data

        Args:
            image_data: Raw image bytes

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(image_data).hexdigest()

    @staticmethod
    def compress_image(image_data: bytes, max_width: int = None) -> bytes:
        """
        Compress and resize image

        Args:
            image_data: Raw image bytes
            max_width: Maximum width in pixels

        Returns:
            Compressed image bytes

        Raises:
            ImageProcessingException: If compression fails
        """
        if max_width is None:
            max_width = ImageService.MAX_WIDTH

        try:
            img = Image.open(BytesIO(image_data))

            # Resize if needed
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {max_width}x{new_height}")

            # Remove EXIF data for privacy
            img_without_exif = Image.new(img.mode, img.size)
            img_without_exif.putdata(list(img.getdata()))

            # Save compressed image
            output = BytesIO()
            save_format = (
                img.format if img.format in ImageService.ALLOWED_FORMATS else "JPEG"
            )
            img_without_exif.save(
                output,
                format=save_format,
                quality=ImageService.COMPRESSION_QUALITY,
                optimize=True,
            )

            compressed_data = output.getvalue()
            logger.info(
                f"Compressed image from {len(image_data)} to "
                f"{len(compressed_data)} bytes "
                f"({len(compressed_data) / len(image_data) * 100:.1f}%)"
            )

            return compressed_data

        except Exception as e:
            raise ImageProcessingException("Failed to compress image", detail=str(e))

    @staticmethod
    def to_base64(image_data: bytes) -> str:
        """
        Convert image bytes to Base64 string

        Args:
            image_data: Raw image bytes

        Returns:
            Base64 encoded string
        """
        if not image_data:
            raise ValidationException("Cannot encode empty image data")
        return base64.b64encode(image_data).decode("utf-8")

    @staticmethod
    def from_base64(base64_str: str) -> bytes:
        """
        Decode Base64 string to image bytes

        Args:
            base64_str: Base64 encoded string

        Returns:
            Raw image bytes

        Raises:
            ValidationException: If decoding fails
        """
        try:
            return base64.b64decode(base64_str)
        except Exception as e:
            raise ValidationException("Invalid base64 data", detail=str(e))

    @staticmethod
    def get_image_info(image_data: bytes) -> dict:
        """
        Get image metadata

        Args:
            image_data: Raw image bytes

        Returns:
            Dictionary with image info (format, size, dimensions)
        """
        try:
            img = Image.open(BytesIO(image_data))
            return {
                "format": img.format,
                "mode": img.mode,
                "size": len(image_data),
                "width": img.width,
                "height": img.height,
                "size_mb": len(image_data) / (1024 * 1024),
            }
        except Exception as e:
            raise ImageProcessingException("Failed to get image info", detail=str(e))
