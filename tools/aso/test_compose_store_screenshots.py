"""compose_store_screenshots.py 的单测。

钉住两件真踩过的事：
1. 大字断行——只按宽度均衡会把 "NI LOCATION, NI / FILE D’ATTENTE" 断在 NI 后面，
   撕开语义；有逗号必须在逗号处断。
2. 成图规格——原截屏 1080x2400（比例 2.22）超 Play 的 2:1 上限会被拒，成图必须是
   1080x1920 RGB（无 alpha）。

运行（仓库根目录）：
  cd backend && poetry run pytest ../tools/aso/test_compose_store_screenshots.py --no-cov
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))

import compose_store_screenshots as c  # noqa: E402


def test_headlines_fit_and_break_at_comma():
    for lang, slides in c.SLIDES.items():
        for s in slides:
            lines, f = c.layout_head(s["head"], lang)
            assert len(lines) <= 2, s["head"]
            assert all(f.getlength(ln) <= c.MAX_TEXT_W for ln in lines), s["head"]
            if len(lines) == 2 and "," in s["head"]:
                assert lines[0].endswith(","), (s["head"], lines)


def test_every_slide_meets_play_spec():
    for lang, slides in c.SLIDES.items():
        assert 2 <= len(slides) <= 8, lang  # Play：每种设备 2–8 张
        for s in slides:
            im = c.compose(lang, s)
            assert im.size == (1080, 1920), s["key"]
            assert im.mode == "RGB", s["key"]  # 无 alpha
            assert max(im.size) / min(im.size) <= 2, s["key"]


def _glyph(f, ch):
    im = Image.new("L", (140, 140), 0)
    ImageDraw.Draw(im).text((10, 10), ch, font=f, fill=255)
    return im.tobytes()


def test_zh_font_subset_covers_every_character():
    """中文字体是子集：文案里加了新字却没重新子集化，会画成空白方框而不报错。"""
    for font_name, key in (
        (c.HEAD_FONT["zh-CN"], "head"),
        (c.SUB_FONT["zh-CN"], "sub"),
    ):
        f = c.font(font_name, 100)
        tofu = _glyph(f, "龘")  # 子集里必然没有
        for s in c.SLIDES["zh-CN"]:
            for ch in s.get(key, "").replace(" ", ""):
                assert _glyph(f, ch) != tofu, (ch, font_name)
