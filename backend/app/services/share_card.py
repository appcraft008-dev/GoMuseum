"""分享图(spec §五)。服务端合成,版式以后改不用发 App。

字体:Noto Sans CJK 的 .ttc 里按语言挑字面(JP/KR/SC/TC 字形不同),拉丁/波兰字母它也全覆盖。
# ponytail: 每次请求现场合成;可分享集合有上限(有正文件数 × 语言),CPU 成问题再落 R2
"""

import io
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

W = 1080
PAD = 64
MAX_IMG_H = 1000
BG = (251, 247, 236)
INK = (44, 35, 22)
SUB = (138, 122, 95)
LINE = (220, 210, 184)
_FACE = {"ja": "JP", "ko": "KR", "zh-hant": "TC"}  # 其余一律 SC


@lru_cache(maxsize=32)
def _font(language: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = settings.SHARE_CARD_FONT_BOLD if bold else settings.SHARE_CARD_FONT
    want = f"Noto Sans CJK {_FACE.get(language, 'SC')}"
    for i in range(12):
        try:
            f = ImageFont.truetype(path, size, index=i)
        except OSError:
            break
        if f.getname()[0] == want:
            return f
    return ImageFont.truetype(path, size)


def first_sentence(text: str, limit: int = 80) -> str:
    s = re.split(r"(?<=[。！？.!?])\s*", text.strip(), maxsplit=1)[0]
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _wrap(draw, text: str, font, width: int, max_lines: int) -> list[str]:
    # 有空格按词断(拉丁),否则按字断(中日韩)。
    # ponytail: 单个超长拉丁词不再拆,会略微出界;真遇到再按字符硬断
    sep = " " if " " in text else ""
    tokens = text.split(" ") if sep else list(text)
    lines, cur = [], ""
    for t in tokens:
        trial = f"{cur}{sep}{t}" if cur else t
        if cur and draw.textlength(trial, font=font) > width:
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


def render_card(
    image: bytes,
    *,
    title: str,
    byline: str,
    excerpt: str,
    footer: str,
    credit: str | None,
    language: str,
) -> bytes:
    art = Image.open(io.BytesIO(image)).convert("RGB")
    art.thumbnail((W, MAX_IMG_H))
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    f_title, f_body, f_small = (
        _font(language, 52, True),
        _font(language, 34),
        _font(language, 26),
    )
    text_w = W - 2 * PAD
    blocks = [
        (_wrap(probe, title, f_title, text_w, 2), f_title, INK, 66),
        (_wrap(probe, byline, f_body, text_w, 1), f_body, SUB, 48),
        (_wrap(probe, f"“{excerpt}”", f_body, text_w, 3), f_body, INK, 50),
    ]
    text_h = sum(len(ls) * lh for ls, _, _, lh in blocks) + 3 * 20
    foot = [footer] + ([credit] if credit else [])
    h = art.height + PAD + text_h + 40 + len(foot) * 38 + PAD
    card = Image.new("RGB", (W, h), BG)
    card.paste(art, ((W - art.width) // 2, 0))
    d = ImageDraw.Draw(card)
    y = art.height + PAD
    for lines, font, color, lh in blocks:
        for line in lines:
            d.text((PAD, y), line, font=font, fill=color)
            y += lh
        y += 20
    d.line((PAD, y, W - PAD, y), fill=LINE, width=2)
    y += 20
    for line in foot:
        d.text((PAD, y), line[:80], font=f_small, fill=SUB)
        y += 38
    buf = io.BytesIO()
    card.save(buf, "PNG", optimize=True)
    return buf.getvalue()
