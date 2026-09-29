"""分享图:中日韩/波兰语不能出方框,输出是 JPEG,文字过长不越界崩溃,二维码画对了。

本地 macOS 没装 Noto 字体时跳过;CI 与 prod 镜像都装 fonts-noto-cjk + fonts-noto-core,
CI 上字体缺失直接判红 —— 否则这组测试会在"哪里都没跑过"的状态下一直绿。
"""

import io
import os
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings

HAS_FONT = all(
    Path(p).exists() for p in (settings.SHARE_CARD_FONT, settings.SHARE_CARD_FONT_LATIN)
)


def test_font_present_in_ci():
    if os.getenv("CI"):
        assert HAS_FONT, "CI 缺分享图字体:ci.yml 没装 fonts-noto-cjk / fonts-noto-core"


needs_font = pytest.mark.skipif(not HAS_FONT, reason="本机无 Noto 字体")


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
        footer="卢浮宫 · GoMuseum",
        credit="Photo: RMN",
        language="zh",
        qr_url="https://gomuseum.app/a/louvre/Q12418?lang=zh&s=qr",
        qr_caption="扫码看讲解",
    )
    img = Image.open(io.BytesIO(png))
    assert img.format == "JPEG"
    assert img.width == 1080 and img.height <= 1600


@needs_font
def test_latin_punctuation_is_not_fullwidth():
    """CJK 字体里 ’ 是全角宽,法语 l’herbe 会裂成 l’ herbe(容器实测过)。"""
    from app.services.share_card import _font

    assert _font("fr", 40).getlength("’") < 20


@needs_font
def test_cjk_wraps_by_char_even_with_spaces():
    """中文里夹空格也按字断 —— 按词断会在「1777」后面折行,第一行只剩半截。"""
    from PIL import ImageDraw

    from app.services.share_card import _font, _wrap

    f = _font("zh", 34)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    text = "这幅小画在 1777 年前后完成，画面里一对恋人在昏暗的卧室中拉扯。"
    lines = _wrap(probe, text, f, 500, 5, "zh")
    assert probe.textlength(lines[0], font=f) > 500 * 0.9


@needs_font
def test_closing_punctuation_never_starts_a_line():
    """staging 实测:「…《草地上的午餐》。”」的 ” 被挤到第二行独占一行。"""
    from PIL import ImageDraw

    from app.services.share_card import _NO_LINE_START, _font, _wrap

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for lang, text in (
        ("zh", "“花一点时间仔细观察一下爱德华·马奈的《草地上的午餐》。”"),
        ("ja", "「エドゥアール・マネの「草上の昼食」をじっくり見てみましょう。」"),
    ):
        lines = _wrap(probe, text, _font(lang, 34), 952, 3, lang)
        assert not any(line[0] in _NO_LINE_START for line in lines[1:]), lines


def test_qr_modules_match_the_url():
    """逐模块采样,与 segno 对同一链接生成的矩阵比对 —— 画错位置/画错链接都会红。
    (不用解码库:不为一条测试引 OpenCV;真实扫码另做过一次性核验。)"""
    import segno

    from app.services.share_card import INK, _qr_image

    url = "https://gomuseum.app/a/orsay/Q152509?lang=zh&s=qr"
    img = _qr_image(url)
    m = segno.make(url, error="m").matrix
    cell = img.width // (len(m) + 4)
    for r, row in enumerate(m):
        for c, v in enumerate(row):
            px = img.getpixel(((c + 2) * cell + cell // 2, (r + 2) * cell + cell // 2))
            assert (px == INK) == bool(v), (r, c)
