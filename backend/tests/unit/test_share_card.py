"""分享图:中日韩/波兰语不能出方框,输出是 PNG,文字过长不越界崩溃。

本地 macOS 没装 Noto CJK 时跳过;CI 与 prod 镜像都装 fonts-noto-cjk,
CI 上字体缺失直接判红 —— 否则这组测试会在"哪里都没跑过"的状态下一直绿。
"""

import io
import os
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings

HAS_FONT = Path(settings.SHARE_CARD_FONT).exists()


def test_font_present_in_ci():
    if os.getenv("CI"):
        assert (
            HAS_FONT
        ), f"CI 缺字体 {settings.SHARE_CARD_FONT}:ci.yml 没装 fonts-noto-cjk"


needs_font = pytest.mark.skipif(not HAS_FONT, reason="本机无 Noto CJK")


def _jpeg(w=800, h=600):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 90, 60)).save(buf, "JPEG")
    return buf.getvalue()


@needs_font
@pytest.mark.parametrize(
    "lang,sample",
    [
        ("zh", "门闩弗拉戈纳尔"),
        ("zh-hant", "門閂導覽"),
        ("ja", "夜警レンブラント"),
        ("ko", "야경 렘브란트"),
        ("pl", "łąśćżźń"),
        ("fr", "œuvre à côté"),
    ],
)
def test_glyphs_exist(lang, sample):
    from app.services.share_card import _font

    f = _font(lang, 40)
    tofu = bytes(f.getmask("\U000f0000"))  # 私用区,必然走 .notdef
    for ch in sample:
        assert bytes(f.getmask(ch)) != tofu, f"{lang} 字体缺字形: {ch!r}"


@needs_font
def test_render_card_png_and_long_text():
    from app.services.share_card import render_card

    png = render_card(
        _jpeg(600, 1400),  # 竖长图要被限高
        title="很长的标题" * 20,
        byline="作者 · 1777",
        excerpt="一句很长的摘要" * 30,
        footer="卢浮宫 · GoMuseum",
        credit="Photo: RMN",
        language="zh",
    )
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    assert img.width == 1080 and img.height <= 1600


def test_first_sentence():
    from app.services.share_card import first_sentence

    assert first_sentence("这是一幅画。它画于 1863 年。") == "这是一幅画。"
    assert first_sentence("One. Two.") == "One."
    assert (
        first_sentence("没有句号" * 50, limit=10) == "没有句号没有句号没…"
    )  # limit 含省略号
