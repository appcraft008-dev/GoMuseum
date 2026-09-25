"""Play 素材规格：图标 512×512 无透明通道 ≤1MB；置顶大图 1024×500 ≤15MB；角标在 48px 下可见。"""

import importlib.util
from pathlib import Path

from PIL import Image

_spec = importlib.util.spec_from_file_location(
    "make_icon", Path(__file__).with_name("make_icon_v1_and_feature_graphic.py")
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _lum(c):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x / 255) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_icon_spec_and_bracket_contrast():
    assert mod.ICON_OUT.stat().st_size < 1_000_000
    im = Image.open(mod.ICON_OUT)
    assert im.size == (512, 512) and im.mode == "RGB"
    bracket = im.getpixel((64 + 40, 64 + 9))  # 左上角标横臂中部
    hi, lo = sorted((_lum(bracket), _lum(mod.CREAM)), reverse=True)
    assert (hi + 0.05) / (lo + 0.05) >= 3  # 旧稿角标只有 1.72


def test_feature_graphics_spec():
    for lang in ("en-US", "fr-FR", "zh-CN"):
        p = mod.FG_DIR / f"{lang}.png"
        assert p.stat().st_size < 15_000_000
        assert Image.open(p).size == (1024, 500)
