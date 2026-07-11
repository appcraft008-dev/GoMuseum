"""预处理:形状/归一化常量/确定性。不 import onnxruntime/torch。"""

import numpy as np
from PIL import Image

from scripts.recognition_bench.embed import PRESETS, preprocess


def test_shapes_and_dtype():
    img = Image.new("RGB", (500, 300), (128, 128, 128))
    for preset in PRESETS:
        x = preprocess(img, preset)
        assert x.shape == (1, 3, 224, 224) and x.dtype == np.float32


def test_normalization_applied():
    img = Image.new("RGB", (300, 300), (255, 255, 255))
    x = preprocess(img, "dinov2")
    expected = (1.0 - 0.485) / 0.229  # 白图 R 通道
    assert abs(float(x[0, 0, 0, 0]) - expected) < 1e-3
