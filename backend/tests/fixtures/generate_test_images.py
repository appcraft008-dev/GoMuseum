"""
Generate test images for image service tests
"""
from PIL import Image
import os

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(SCRIPT_DIR, "test_images")

# Create directory if it doesn't exist
os.makedirs(IMAGE_DIR, exist_ok=True)

# 1. Generate 1KB JPEG (100x100 pixels)
img_small_jpeg = Image.new('RGB', (100, 100), color='red')
jpeg_path = os.path.join(IMAGE_DIR, 'valid_jpeg_1kb.jpg')
img_small_jpeg.save(jpeg_path, 'JPEG', quality=85)
print(f"Created: {jpeg_path} ({os.path.getsize(jpeg_path)} bytes)")

# 2. Generate 500KB PNG (1000x1000 pixels)
img_large_png = Image.new('RGB', (1000, 1000), color='blue')
png_path = os.path.join(IMAGE_DIR, 'valid_png_500kb.png')
img_large_png.save(png_path, 'PNG')
print(f"Created: {png_path} ({os.path.getsize(png_path)} bytes)")

# 3. Generate 2MB large JPEG (2000x2000 pixels)
img_large_jpeg = Image.new('RGB', (2000, 2000), color='green')
large_jpeg_path = os.path.join(IMAGE_DIR, 'large_image_2mb.jpg')
img_large_jpeg.save(large_jpeg_path, 'JPEG', quality=95)
print(f"Created: {large_jpeg_path} ({os.path.getsize(large_jpeg_path)} bytes)")

# 4. Generate corrupted data file
corrupted_path = os.path.join(IMAGE_DIR, 'corrupted.dat')
with open(corrupted_path, 'wb') as f:
    f.write(b'INVALID_IMAGE_DATA_NOT_A_REAL_IMAGE_FILE')
print(f"Created: {corrupted_path} ({os.path.getsize(corrupted_path)} bytes)")

# 5. Generate tiny JPEG (10x10 pixels)
img_tiny = Image.new('RGB', (10, 10), color='yellow')
tiny_path = os.path.join(IMAGE_DIR, 'tiny_10x10.jpg')
img_tiny.save(tiny_path, 'JPEG')
print(f"Created: {tiny_path} ({os.path.getsize(tiny_path)} bytes)")

# 6. Generate wide image for resize testing (3000x1000 pixels)
img_wide = Image.new('RGB', (3000, 1000), color='purple')
wide_path = os.path.join(IMAGE_DIR, 'wide_3000x1000.jpg')
img_wide.save(wide_path, 'JPEG', quality=90)
print(f"Created: {wide_path} ({os.path.getsize(wide_path)} bytes)")

print(f"\n✅ All test images generated in: {IMAGE_DIR}")
