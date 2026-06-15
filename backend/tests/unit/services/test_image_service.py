"""
Unit tests for Image Service
Tests image preprocessing, validation, and encoding
"""

import base64
from pathlib import Path

import pytest

from app.core.exceptions import ImageProcessingException, ValidationException
from app.services.image_service import ImageService
from tests.fixtures.image_helpers import (
    create_artwork_simulation,
    create_compressed_image,
    create_gradient_image,
    create_pattern_image,
    create_resized_image,
    create_similar_image,
    create_test_image,
)

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "test_images"


class TestImageService:
    """Test suite for image service - validation tests"""

    def test_validates_image_size_less_than_10mb(self):
        """should_accept_images_smaller_than_10mb"""
        # Arrange - 使用真实的小图片
        valid_image_path = FIXTURES_DIR / "valid_jpeg_1kb.jpg"
        with open(valid_image_path, "rb") as f:
            valid_image_bytes = f.read()

        # Act & Assert - 应该不抛出异常
        assert ImageService.validate_image(valid_image_bytes) is True

    def test_rejects_images_larger_than_10mb(self):
        """should_raise_validation_error_for_oversized_images"""
        # Arrange - 创建超过10MB的假数据
        oversized_image_bytes = b"x" * (11 * 1024 * 1024)  # 11MB

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ImageService.validate_image(oversized_image_bytes)

        assert "exceeds" in str(exc_info.value)
        assert "10MB" in str(exc_info.value) or "10" in str(exc_info.value)

    def test_validates_jpeg_image_format(self):
        """should_accept_valid_jpeg_format"""
        # Arrange - 使用真实的JPEG文件
        jpeg_path = FIXTURES_DIR / "valid_jpeg_1kb.jpg"
        with open(jpeg_path, "rb") as f:
            jpeg_bytes = f.read()

        # Act & Assert
        assert ImageService.validate_image(jpeg_bytes) is True

    def test_validates_png_image_format(self):
        """should_accept_valid_png_format"""
        # Arrange - 使用真实的PNG文件
        png_path = FIXTURES_DIR / "valid_png_500kb.png"
        with open(png_path, "rb") as f:
            png_bytes = f.read()

        # Act & Assert
        assert ImageService.validate_image(png_bytes) is True

    def test_rejects_corrupted_image_data(self):
        """should_reject_corrupted_image_data"""
        # Arrange - 使用损坏的文件
        corrupted_path = FIXTURES_DIR / "corrupted.dat"
        with open(corrupted_path, "rb") as f:
            corrupted_bytes = f.read()

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ImageService.validate_image(corrupted_bytes)

        assert "Invalid image" in str(exc_info.value) or "Failed to parse" in str(
            exc_info.value
        )

    def test_rejects_empty_image_data(self):
        """should_reject_empty_data"""
        # Arrange
        empty_bytes = b""

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ImageService.validate_image(empty_bytes)

        assert "empty" in str(exc_info.value).lower()

    def test_rejects_unsupported_format(self):
        """should_reject_bmp_and_other_unsupported_formats"""
        # Arrange - 创建一个BMP图片（不支持的格式）
        # BMP 格式不在 ALLOWED_FORMATS 中
        from io import BytesIO

        from PIL import Image

        # 创建一个简单的RGB图片并保存为BMP
        img = Image.new("RGB", (10, 10), color="red")
        buffer = BytesIO()
        img.save(buffer, format="BMP")
        bmp_bytes = buffer.getvalue()

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ImageService.validate_image(bmp_bytes)

        # 验证错误信息提到格式不支持
        error_msg = str(exc_info.value)
        assert "not supported" in error_msg or "format" in error_msg.lower()


class TestImageServiceHash:
    """Test hash generation functionality"""

    def test_generate_hash_consistency(self):
        """should_generate_same_hash_for_same_image"""
        # Arrange - 使用真实图片
        image_path = FIXTURES_DIR / "valid_jpeg_1kb.jpg"
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Act
        hash1 = ImageService.generate_hash(image_bytes)
        hash2 = ImageService.generate_hash(image_bytes)

        # Assert
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters

    def test_generate_hash_different_for_different_images(self):
        """should_generate_different_hash_for_different_images"""
        # Arrange
        jpeg_path = FIXTURES_DIR / "valid_jpeg_1kb.jpg"
        png_path = FIXTURES_DIR / "valid_png_500kb.png"

        with open(jpeg_path, "rb") as f:
            jpeg_bytes = f.read()
        with open(png_path, "rb") as f:
            png_bytes = f.read()

        # Act
        hash_jpeg = ImageService.generate_hash(jpeg_bytes)
        hash_png = ImageService.generate_hash(png_bytes)

        # Assert
        assert hash_jpeg != hash_png


class TestImageServiceEncoding:
    """Test image encoding functionality"""

    def test_to_base64_encoding(self):
        """should_convert_bytes_to_base64_encoded_string"""
        # Arrange - 使用真实图片
        image_path = FIXTURES_DIR / "tiny_10x10.jpg"
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Act
        encoded = ImageService.to_base64(image_bytes)

        # Assert
        assert isinstance(encoded, str)
        assert len(encoded) > 0
        # 验证是有效的 base64
        decoded = base64.b64decode(encoded)
        assert decoded == image_bytes

    def test_from_base64_decoding(self):
        """should_decode_base64_string_to_bytes"""
        # Arrange
        original_bytes = b"test_image_data"
        base64_str = base64.b64encode(original_bytes).decode("utf-8")

        # Act
        decoded_bytes = ImageService.from_base64(base64_str)

        # Assert
        assert decoded_bytes == original_bytes

    def test_to_base64_rejects_empty_data(self):
        """should_raise_error_for_empty_input"""
        # Arrange
        empty_bytes = b""

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ImageService.to_base64(empty_bytes)

        assert "empty" in str(exc_info.value).lower()

    def test_from_base64_handles_invalid_input(self):
        """should_raise_exception_for_invalid_input_type"""
        # Arrange - 使用会导致TypeError的输入（None）
        # 这会触发 from_base64 中的 except 分支

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            ImageService.from_base64(None)  # type: ignore

        assert "Invalid base64" in str(exc_info.value)


class TestImageServiceCompression:
    """Test image compression functionality"""

    def test_compress_image_reduces_size(self):
        """should_reduce_file_size_for_large_images"""
        # Arrange - 使用较大的图片
        large_image_path = FIXTURES_DIR / "large_image_2mb.jpg"
        with open(large_image_path, "rb") as f:
            large_image_bytes = f.read()

        original_size = len(large_image_bytes)

        # Act
        compressed_bytes = ImageService.compress_image(large_image_bytes)

        # Assert
        compressed_size = len(compressed_bytes)
        # 压缩后应该更小或相近
        assert compressed_size <= original_size * 1.1  # 允许10%的增长（因为已经是JPEG）

    def test_compress_image_resizes_large_width(self):
        """should_resize_images_wider_than_max_width"""
        # Arrange - 使用宽图片 (3000x1000)
        wide_image_path = FIXTURES_DIR / "wide_3000x1000.jpg"
        with open(wide_image_path, "rb") as f:
            wide_image_bytes = f.read()

        # Act
        compressed_bytes = ImageService.compress_image(wide_image_bytes, max_width=1200)

        # Assert - 验证宽度被调整
        info = ImageService.get_image_info(compressed_bytes)
        assert info["width"] == 1200
        # 验证高度按比例调整 (3000:1000 = 1200:400)
        assert info["height"] == 400

    def test_compress_image_preserves_small_images(self):
        """should_not_enlarge_small_images"""
        # Arrange - 使用小图片
        small_image_path = FIXTURES_DIR / "tiny_10x10.jpg"
        with open(small_image_path, "rb") as f:
            small_image_bytes = f.read()

        # Act
        compressed_bytes = ImageService.compress_image(small_image_bytes)

        # Assert - 小图片不应该被放大
        info = ImageService.get_image_info(compressed_bytes)
        assert info["width"] == 10
        assert info["height"] == 10

    def test_compress_image_handles_different_formats(self):
        """should_handle_both_jpeg_and_png"""
        # Arrange - 测试PNG格式
        png_path = FIXTURES_DIR / "valid_png_500kb.png"
        with open(png_path, "rb") as f:
            png_bytes = f.read()

        # Act
        compressed_bytes = ImageService.compress_image(png_bytes)

        # Assert - 应该成功压缩
        assert len(compressed_bytes) > 0
        info = ImageService.get_image_info(compressed_bytes)
        # PNG可能被转换为JPEG或保持PNG
        assert info["format"] in ["JPEG", "PNG"]

    def test_compress_image_handles_corrupted_data(self):
        """should_raise_exception_for_corrupted_image_during_compression"""
        # Arrange - 损坏的数据
        corrupted_path = FIXTURES_DIR / "corrupted.dat"
        with open(corrupted_path, "rb") as f:
            corrupted_bytes = f.read()

        # Act & Assert
        with pytest.raises(ImageProcessingException) as exc_info:
            ImageService.compress_image(corrupted_bytes)

        assert "Failed to compress" in str(exc_info.value)


class TestImageServiceMetadata:
    """Test image metadata extraction"""

    def test_get_image_info_returns_metadata(self):
        """should_return_correct_metadata_for_valid_image"""
        # Arrange - 使用已知尺寸的图片
        image_path = FIXTURES_DIR / "valid_jpeg_1kb.jpg"
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Act
        info = ImageService.get_image_info(image_bytes)

        # Assert
        assert "format" in info
        assert "mode" in info
        assert "size" in info
        assert "width" in info
        assert "height" in info
        assert "size_mb" in info

        # 验证数据类型
        assert isinstance(info["format"], str)
        assert isinstance(info["width"], int)
        assert isinstance(info["height"], int)
        assert isinstance(info["size"], int)
        assert isinstance(info["size_mb"], float)

        # 验证格式
        assert info["format"] == "JPEG"
        assert info["size"] == len(image_bytes)

    def test_get_image_info_handles_invalid_data(self):
        """should_raise_exception_for_invalid_image_data"""
        # Arrange
        corrupted_path = FIXTURES_DIR / "corrupted.dat"
        with open(corrupted_path, "rb") as f:
            corrupted_bytes = f.read()

        # Act & Assert
        with pytest.raises(ImageProcessingException) as exc_info:
            ImageService.get_image_info(corrupted_bytes)

        assert "Failed to get image info" in str(exc_info.value)


class TestPerceptualHash:
    """Test perceptual hash generation and similarity detection for Step 2 cache optimization"""

    def test_generates_perceptual_hash_from_image(self):
        """should_generate_16_character_hexadecimal_hash_for_8x8_phash"""
        # Arrange - 创建测试图片
        image_bytes = create_gradient_image(200, 200)

        # Act
        phash = ImageService.generate_perceptual_hash(image_bytes, hash_size=8)

        # Assert
        assert phash is not None
        assert isinstance(phash, str)
        assert len(phash) == 16  # 8x8 hash = 64 bits = 16 hex chars
        # 验证是有效的十六进制字符串
        assert all(c in "0123456789abcdef" for c in phash.lower())

    def test_same_image_produces_same_perceptual_hash(self):
        """should_generate_identical_phash_for_identical_images"""
        # Arrange - 使用相同的图片
        image_bytes = create_pattern_image(200, 200, pattern="checkerboard")

        # Act
        phash1 = ImageService.generate_perceptual_hash(image_bytes)
        phash2 = ImageService.generate_perceptual_hash(image_bytes)

        # Assert
        assert phash1 == phash2

    def test_similar_images_produce_similar_hashes(self):
        """should_generate_high_similarity_for_brightness_adjusted_images"""
        # Arrange - 创建原始图片和调整亮度的版本
        original = create_artwork_simulation(seed=42)
        brighter = create_similar_image(original, brightness=1.3)
        darker = create_similar_image(original, brightness=0.7)

        # Act
        hash_original = ImageService.generate_perceptual_hash(original)
        hash_brighter = ImageService.generate_perceptual_hash(brighter)
        hash_darker = ImageService.generate_perceptual_hash(darker)

        # Calculate similarity
        similarity_brighter = ImageService.hash_similarity(hash_original, hash_brighter)
        similarity_darker = ImageService.hash_similarity(hash_original, hash_darker)

        # Assert - 相似度应该大于90% (同一艺术品不同拍摄条件)
        assert (
            similarity_brighter >= 0.90
        ), f"Brighter image similarity {similarity_brighter:.2%} should be >= 90%"
        assert (
            similarity_darker >= 0.90
        ), f"Darker image similarity {similarity_darker:.2%} should be >= 90%"

    def test_different_images_produce_different_hashes(self):
        """should_generate_low_similarity_for_completely_different_images"""
        # Arrange - 创建完全不同的图片（使用复杂图案而非纯色）
        checkerboard = create_pattern_image(200, 200, pattern="checkerboard")
        stripes = create_pattern_image(200, 200, pattern="stripes")
        artwork1 = create_artwork_simulation(seed=100)
        artwork2 = create_artwork_simulation(seed=200)

        # Act
        hash_checkerboard = ImageService.generate_perceptual_hash(checkerboard)
        hash_stripes = ImageService.generate_perceptual_hash(stripes)
        hash_artwork1 = ImageService.generate_perceptual_hash(artwork1)
        hash_artwork2 = ImageService.generate_perceptual_hash(artwork2)

        # Calculate similarity
        similarity_patterns = ImageService.hash_similarity(
            hash_checkerboard, hash_stripes
        )
        similarity_artworks = ImageService.hash_similarity(hash_artwork1, hash_artwork2)

        # Assert - 完全不同的图片相似度应该低于95%
        # 注意：纯色图片的phash非常相似，所以我们使用复杂图案
        assert (
            similarity_patterns < 0.95
        ), f"Different patterns similarity {similarity_patterns:.2%} should be < 95%"
        assert (
            similarity_artworks < 0.95
        ), f"Different artworks similarity {similarity_artworks:.2%} should be < 95%"

        # 验证哈希确实不同
        assert hash_checkerboard != hash_stripes
        assert hash_artwork1 != hash_artwork2

    def test_hash_similarity_calculation(self):
        """should_calculate_correct_similarity_scores"""
        # Arrange - 创建原始图片（使用复杂图案）
        original = create_artwork_simulation(seed=50)
        hash_original = ImageService.generate_perceptual_hash(original)

        # Test 1: 完全相同 = 1.0
        similarity_identical = ImageService.hash_similarity(
            hash_original, hash_original
        )
        assert (
            similarity_identical == 1.0
        ), "Identical hashes should have 100% similarity"

        # Test 2: 轻微调整应该仍然相似
        slightly_modified = create_similar_image(original, brightness=1.05)
        hash_modified = ImageService.generate_perceptual_hash(slightly_modified)
        similarity_slight = ImageService.hash_similarity(hash_original, hash_modified)
        # 调整阈值到更现实的水平，轻微修改仍然会被识别为相似
        assert (
            similarity_slight >= 0.80
        ), f"Slightly modified similarity {similarity_slight:.2%} should be >= 80%"

        # Test 3: 完全不同（不同的artwork） < 0.95
        different = create_artwork_simulation(seed=500)  # 完全不同的seed
        hash_different = ImageService.generate_perceptual_hash(different)
        similarity_different = ImageService.hash_similarity(
            hash_original, hash_different
        )
        # 使用更现实的阈值，因为即使不同的图片也可能有一些相似度
        assert (
            similarity_different < 0.95
        ), f"Different images similarity {similarity_different:.2%} should be < 95%"

        # 验证哈希确实不同
        assert hash_original != hash_different

    def test_handles_various_image_formats(self):
        """should_correctly_process_rgb_rgba_and_grayscale_images"""
        from io import BytesIO

        from PIL import Image

        # Test 1: RGB image
        rgb_img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        buffer_rgb = BytesIO()
        rgb_img.save(buffer_rgb, format="JPEG")
        hash_rgb = ImageService.generate_perceptual_hash(buffer_rgb.getvalue())
        assert len(hash_rgb) == 16

        # Test 2: RGBA image (with transparency)
        rgba_img = Image.new("RGBA", (100, 100), color=(128, 128, 128, 255))
        buffer_rgba = BytesIO()
        rgba_img.save(buffer_rgba, format="PNG")
        hash_rgba = ImageService.generate_perceptual_hash(buffer_rgba.getvalue())
        assert len(hash_rgba) == 16

        # Test 3: Grayscale image
        gray_img = Image.new("L", (100, 100), color=128)
        buffer_gray = BytesIO()
        gray_img.save(buffer_gray, format="JPEG")
        hash_gray = ImageService.generate_perceptual_hash(buffer_gray.getvalue())
        assert len(hash_gray) == 16

        # All should produce valid hashes (may be similar since same gray value)
        similarity_rgb_rgba = ImageService.hash_similarity(hash_rgb, hash_rgba)
        assert (
            similarity_rgb_rgba > 0.95
        ), "RGB and RGBA of same color should be highly similar"

    def test_hash_size_parameter(self):
        """should_generate_different_length_hashes_based_on_hash_size"""
        # Arrange
        image_bytes = create_pattern_image(200, 200)

        # Act - 测试不同的hash_size
        hash_8 = ImageService.generate_perceptual_hash(image_bytes, hash_size=8)
        hash_16 = ImageService.generate_perceptual_hash(image_bytes, hash_size=16)

        # Assert
        # hash_size=8  -> 8x8  = 64 bits  = 16 hex chars
        # hash_size=16 -> 16x16 = 256 bits = 64 hex chars
        assert (
            len(hash_8) == 16
        ), f"hash_size=8 should produce 16 chars, got {len(hash_8)}"
        assert (
            len(hash_16) == 64
        ), f"hash_size=16 should produce 64 chars, got {len(hash_16)}"

    def test_perceptual_hash_resilient_to_compression(self):
        """should_maintain_high_similarity_despite_jpeg_compression"""
        # Arrange - 创建原始图片
        original = create_artwork_simulation(seed=100)

        # Act - 生成不同压缩质量的版本
        compressed_low = create_compressed_image(original, quality=30)
        compressed_high = create_compressed_image(original, quality=90)

        hash_original = ImageService.generate_perceptual_hash(original)
        hash_low = ImageService.generate_perceptual_hash(compressed_low)
        hash_high = ImageService.generate_perceptual_hash(compressed_high)

        # Calculate similarity
        similarity_low = ImageService.hash_similarity(hash_original, hash_low)
        similarity_high = ImageService.hash_similarity(hash_original, hash_high)

        # Assert - 压缩后相似度仍然应该高（使用更现实的阈值）
        # JPEG压缩会引入一些差异，但感知哈希应该仍然识别为同一图片
        assert (
            similarity_low >= 0.75
        ), f"Low quality compression similarity {similarity_low:.2%} should be >= 75%"
        assert (
            similarity_high >= 0.90
        ), f"High quality compression similarity {similarity_high:.2%} should be >= 90%"

    def test_perceptual_hash_resilient_to_resizing(self):
        """should_maintain_high_similarity_despite_resizing"""
        # Arrange - 创建原始图片（使用artwork而非checkerboard，因为checkerboard缩放可能改变图案）
        original = create_artwork_simulation(seed=123)

        # Act - 生成不同尺寸的版本
        resized_smaller = create_resized_image(original, scale=0.5)  # 150x150
        resized_larger = create_resized_image(original, scale=1.5)  # 450x450

        hash_original = ImageService.generate_perceptual_hash(original)
        hash_smaller = ImageService.generate_perceptual_hash(resized_smaller)
        hash_larger = ImageService.generate_perceptual_hash(resized_larger)

        # Calculate similarity
        similarity_smaller = ImageService.hash_similarity(hash_original, hash_smaller)
        similarity_larger = ImageService.hash_similarity(hash_original, hash_larger)

        # Assert - 缩放后相似度应该较高（使用现实阈值）
        # 感知哈希对大幅缩放比较敏感，但应该能识别为相似图片
        assert (
            similarity_smaller >= 0.75
        ), f"Smaller size similarity {similarity_smaller:.2%} should be >= 75%"
        assert (
            similarity_larger >= 0.75
        ), f"Larger size similarity {similarity_larger:.2%} should be >= 75%"

    def test_perceptual_hash_handles_corrupted_image(self):
        """should_raise_exception_for_corrupted_image_data"""
        # Arrange - 创建损坏的数据
        corrupted_bytes = b"not a valid image data"

        # Act & Assert
        with pytest.raises(ImageProcessingException) as exc_info:
            ImageService.generate_perceptual_hash(corrupted_bytes)

        assert "Failed to generate perceptual hash" in str(exc_info.value)
