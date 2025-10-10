"""
Test helper functions for generating test images
Provides utilities for creating images with different similarity levels
"""
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
from typing import Tuple


def create_test_image(
    width: int = 100,
    height: int = 100,
    color: Tuple[int, int, int] = (255, 0, 0),
    format: str = "JPEG"
) -> bytes:
    """
    Create a solid color test image

    Args:
        width: Image width in pixels
        height: Image height in pixels
        color: RGB color tuple (default red)
        format: Image format (JPEG or PNG)

    Returns:
        Image data as bytes

    Example:
        >>> red_image = create_test_image(100, 100, (255, 0, 0))
        >>> blue_image = create_test_image(200, 200, (0, 0, 255), "PNG")
    """
    img = Image.new('RGB', (width, height), color=color)
    buffer = BytesIO()
    img.save(buffer, format=format, quality=85)
    return buffer.getvalue()


def create_gradient_image(
    width: int = 200,
    height: int = 200,
    start_color: Tuple[int, int, int] = (0, 0, 0),
    end_color: Tuple[int, int, int] = (255, 255, 255),
    format: str = "JPEG"
) -> bytes:
    """
    Create a gradient test image from start_color to end_color

    Args:
        width: Image width in pixels
        height: Image height in pixels
        start_color: Starting RGB color
        end_color: Ending RGB color
        format: Image format

    Returns:
        Image data as bytes
    """
    img = Image.new('RGB', (width, height))
    pixels = img.load()

    for y in range(height):
        for x in range(width):
            # Calculate gradient
            ratio = x / width
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            pixels[x, y] = (r, g, b)

    buffer = BytesIO()
    img.save(buffer, format=format, quality=85)
    return buffer.getvalue()


def create_pattern_image(
    width: int = 200,
    height: int = 200,
    pattern: str = "checkerboard",
    format: str = "JPEG"
) -> bytes:
    """
    Create a patterned test image (checkerboard, stripes, etc.)

    Args:
        width: Image width in pixels
        height: Image height in pixels
        pattern: Pattern type ("checkerboard" or "stripes")
        format: Image format

    Returns:
        Image data as bytes
    """
    img = Image.new('RGB', (width, height))
    pixels = img.load()

    if pattern == "checkerboard":
        square_size = 20
        for y in range(height):
            for x in range(width):
                if (x // square_size + y // square_size) % 2 == 0:
                    pixels[x, y] = (255, 255, 255)  # White
                else:
                    pixels[x, y] = (0, 0, 0)  # Black

    elif pattern == "stripes":
        stripe_width = 20
        for y in range(height):
            for x in range(width):
                if (x // stripe_width) % 2 == 0:
                    pixels[x, y] = (255, 0, 0)  # Red
                else:
                    pixels[x, y] = (0, 0, 255)  # Blue

    buffer = BytesIO()
    img.save(buffer, format=format, quality=85)
    return buffer.getvalue()


def create_similar_image(
    original_image_bytes: bytes,
    brightness: float = 1.2,
    contrast: float = 1.0,
    blur: float = 0.0,
    rotation: float = 0.0,
    format: str = "JPEG"
) -> bytes:
    """
    Create a similar version of an image with adjustments

    This simulates the same artwork photographed under different conditions:
    - Different lighting (brightness)
    - Different camera settings (contrast)
    - Slight motion blur (blur)
    - Different angle (rotation)

    Args:
        original_image_bytes: Original image data
        brightness: Brightness multiplier (1.0 = no change, 1.2 = 20% brighter)
        contrast: Contrast multiplier (1.0 = no change)
        blur: Blur radius (0.0 = no blur, higher = more blur)
        rotation: Rotation angle in degrees (0.0 = no rotation)
        format: Output image format

    Returns:
        Modified image data as bytes

    Example:
        >>> original = create_gradient_image()
        >>> brighter = create_similar_image(original, brightness=1.3)
        >>> darker = create_similar_image(original, brightness=0.8)
        >>> blurred = create_similar_image(original, blur=2.0)
    """
    img = Image.open(BytesIO(original_image_bytes))

    # Convert to RGB if necessary
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Apply brightness adjustment
    if brightness != 1.0:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(brightness)

    # Apply contrast adjustment
    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast)

    # Apply blur
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))

    # Apply rotation
    if rotation != 0.0:
        img = img.rotate(rotation, expand=False, fillcolor=(255, 255, 255))

    # Save modified image
    buffer = BytesIO()
    img.save(buffer, format=format, quality=85)
    return buffer.getvalue()


def create_resized_image(
    original_image_bytes: bytes,
    scale: float = 0.5,
    format: str = "JPEG"
) -> bytes:
    """
    Create a resized version of an image

    Args:
        original_image_bytes: Original image data
        scale: Scale factor (0.5 = half size, 2.0 = double size)
        format: Output image format

    Returns:
        Resized image data as bytes
    """
    img = Image.open(BytesIO(original_image_bytes))

    new_width = int(img.width * scale)
    new_height = int(img.height * scale)

    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    resized.save(buffer, format=format, quality=85)
    return buffer.getvalue()


def create_compressed_image(
    original_image_bytes: bytes,
    quality: int = 50,
    format: str = "JPEG"
) -> bytes:
    """
    Create a compressed version of an image with different quality

    Args:
        original_image_bytes: Original image data
        quality: JPEG quality (1-100, lower = more compression)
        format: Output image format

    Returns:
        Compressed image data as bytes
    """
    img = Image.open(BytesIO(original_image_bytes))

    buffer = BytesIO()
    img.save(buffer, format=format, quality=quality, optimize=True)
    return buffer.getvalue()


def create_artwork_simulation(seed: int = 42) -> bytes:
    """
    Create a simulated artwork image with complex patterns

    This creates a more realistic test image that simulates an actual artwork
    with multiple colors and patterns.

    Args:
        seed: Random seed for reproducible results

    Returns:
        Simulated artwork image as bytes
    """
    import random
    random.seed(seed)

    width, height = 300, 300
    img = Image.new('RGB', (width, height))
    pixels = img.load()

    # Create a multi-colored pattern
    for y in range(height):
        for x in range(width):
            # Create concentric circles pattern
            center_x, center_y = width // 2, height // 2
            distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5

            r = int((distance / 3) % 256)
            g = int((distance / 2) % 256)
            b = int((distance / 4) % 256)

            # Add some noise
            r = min(255, max(0, r + random.randint(-20, 20)))
            g = min(255, max(0, g + random.randint(-20, 20)))
            b = min(255, max(0, b + random.randint(-20, 20)))

            pixels[x, y] = (r, g, b)

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()
