"""合成畸变:官方图→伪游客照(透视/反光/裁切/模糊/暗光),固定seed可复现。"""

import numpy as np
from PIL import Image

from scripts.recognition_bench.distort import distort_all


def _img():
    # 必须非纯色(纯色图 blur 后逐字节相同)且确定性(effect_noise 无 seed 不可用)
    a = (np.arange(320 * 240 * 3) % 255).astype("uint8").reshape(240, 320, 3)
    return Image.fromarray(a)


def test_five_variants_same_size_rgb():
    out = distort_all(_img(), seed=42)
    assert set(out) == {"perspective", "glare", "crop", "blur", "dark"}
    for v in out.values():
        assert v.size == (320, 240) and v.mode == "RGB"


def test_deterministic():
    a = distort_all(_img(), seed=42)["perspective"].tobytes()
    b = distort_all(_img(), seed=42)["perspective"].tobytes()
    assert a == b


def test_actually_changes_pixels():
    src = _img().tobytes()
    out = distort_all(_img(), seed=42)
    assert all(v.tobytes() != src for v in out.values())
