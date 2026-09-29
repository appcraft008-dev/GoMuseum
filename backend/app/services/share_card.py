"""分享图(spec §五)。服务端合成,版式以后改不用发 App。

字体:中日韩用 Noto Sans CJK 的 .ttc 按语言挑字面(JP/KR/SC/TC 字形不同);
其余语种用 Noto Sans —— CJK 字体的拉丁部分缺波兰字母(ł ą ś…出方框),
且 ’ “ · 是全角宽度(法语 l’herbe 会裂成 l’ herbe)。2026-09-29 容器实测。
# ponytail: 路由层进程内 LRU 缓存合成结果(见 share_pages._card_bytes);多机部署再考虑落 R2
"""

import io
from functools import lru_cache

import segno
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

W = 1080
PAD = 64
MAX_IMG_H = 940  # 文字最满时整张仍 ≤1600 高(聊天预览不被裁成一条)
BG = (251, 247, 236)
INK = (44, 35, 22)
SUB = (138, 122, 95)
LINE = (220, 210, 184)
_FACE = {"zh": "SC", "zh-hant": "TC", "ja": "JP", "ko": "KR"}
_NO_LINE_START = set(
    "，。、．！？：；）」』》〉】”’…ゃゅょぁぃぅぇぉっャュョァィゥェォッー々"
)


@lru_cache(maxsize=32)
def _font(language: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if language not in _FACE:
        path = (
            settings.SHARE_CARD_FONT_LATIN_BOLD
            if bold
            else settings.SHARE_CARD_FONT_LATIN
        )
        return ImageFont.truetype(path, size)
    path = settings.SHARE_CARD_FONT_BOLD if bold else settings.SHARE_CARD_FONT
    want = f"Noto Sans CJK {_FACE[language]}"
    for i in range(12):
        try:
            f = ImageFont.truetype(path, size, index=i)
        except OSError:
            break
        if f.getname()[0] == want:
            return f
    return ImageFont.truetype(path, size)


def _wrap(
    draw, text: str, font, width: int, max_lines: int, language: str
) -> list[str]:
    # 中日韩按字断,其余按词断。按语言判不按"有没有空格"判:中文里常夹空格
    # ("这幅小画在 1777 年…"),按词断会在 1777 后面折行。
    # ponytail: 单个超长拉丁词不再拆,会略微出界;真遇到再按字符硬断
    sep = "" if language in _FACE else " "
    tokens = text.split(" ") if sep else list(text)
    lines, cur = [], ""
    for t in tokens:
        trial = f"{cur}{sep}{t}" if cur else t
        # 避头:收尾标点/小假名不许开新行,挂在上一行行尾(略超一字宽,落在右边距里)
        if (
            cur
            and t not in _NO_LINE_START
            and draw.textlength(trial, font=font) > width
        ):
            lines.append(cur)
            cur = t
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip()[:-1] + "…"
    return lines


QR = 176  # 二维码边长(px);一件作品的链接 ~60 字符 → 29-33 模块,每模块 ≥5px 手机好扫


def _qr_image(url: str, size: int = QR) -> Image.Image:
    """链接 → 二维码图(墨色模块、纸色底,带 2 模块静区)。模块按整数像素画,扫得稳。"""
    m = segno.make(url, error="m").matrix
    n = len(m) + 4
    cell = max(1, size // n)
    img = Image.new("RGB", (n * cell, n * cell), BG)
    d = ImageDraw.Draw(img)
    for r, row in enumerate(m):
        for c, v in enumerate(row):
            if v:
                x, y = (c + 2) * cell, (r + 2) * cell
                d.rectangle((x, y, x + cell - 1, y + cell - 1), fill=INK)
    return img


def render_card(
    image: bytes,
    *,
    title: str,
    byline: str,
    footer: str,
    credit: str | None,
    language: str,
    qr_url: str,
    qr_caption: str,
) -> bytes:
    """JPEG。右下角二维码:微信收图会丢掉附带的链接文字,扫码是唯一回到网页的路。"""
    art = Image.open(io.BytesIO(image)).convert("RGB")
    art.thumbnail((W, MAX_IMG_H))
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    f_title, f_body, f_small = (
        _font(language, 52, True),
        _font(language, 34),
        _font(language, 26),
    )
    qr = _qr_image(qr_url)
    text_w = W - 2 * PAD - qr.width - 32
    foot = [footer] + ([credit] if credit else [])
    blocks = [
        (_wrap(probe, title, f_title, text_w, 2, language), f_title, INK, 66),
        (_wrap(probe, byline, f_body, text_w, 1, language), f_body, SUB, 48),
    ]
    text_h = sum(len(ls) * lh for ls, _, _, lh in blocks) + len(blocks) * 20
    text_h += 40 + len(foot) * 38
    qr_h = qr.height + 38
    h = art.height + PAD + max(text_h, qr_h) + PAD
    card = Image.new("RGB", (W, h), BG)
    card.paste(art, ((W - art.width) // 2, 0))
    d = ImageDraw.Draw(card)
    top = y = art.height + PAD
    for lines, font, color, lh in blocks:
        for line in lines:
            d.text((PAD, y), line, font=font, fill=color)
            y += lh
        y += 20
    d.line((PAD, y, PAD + text_w, y), fill=LINE, width=2)
    y += 20
    for line in foot:
        d.text(
            (PAD, y),
            _wrap(probe, line, f_small, text_w, 1, language)[0],
            font=f_small,
            fill=SUB,
        )
        y += 38
    qx = W - PAD - qr.width
    card.paste(qr, (qx, top))
    cap_w = d.textlength(qr_caption, font=f_small)
    d.text(
        (qx + (qr.width - cap_w) / 2, top + qr.height + 4),
        qr_caption,
        font=f_small,
        fill=SUB,
    )
    buf = io.BytesIO()
    # JPEG 不是 PNG:照片为主的图 PNG 要 1.2MB、optimize 编码 0.6s;JPEG q88 ~200KB、编码 ~3ms
    card.save(buf, "JPEG", quality=88)
    return buf.getvalue()
