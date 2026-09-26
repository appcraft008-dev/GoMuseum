"""把真实截图合成为可直接上传 Google Play 的商店图（1080x1920 PNG）。

为什么是脚本而不是让生成模型画：
  手机界面里的每个像素必须来自真实 App 截图——画错了就是「商店素材与实际功能
  不符」。脚本只做确定性的事：裁掉状态栏、缩放、圆角、投影、排大字。文案改了
  重跑一遍即可。

唯一「画」出来的东西是 NO RENTAL 那张里的通用租借讲解器（纯几何图形，不复刻任何
真实设备）。

用法（在仓库根目录）：
  poetry -C backend run python tools/aso/compose_store_screenshots.py
  加 --contact 额外输出一张缩略对照图（用来检验「缩到 25% 还读得出大字」）。

规格来源：docs/marketing/aso/google-play-round1/creative-brief-en-fr.md §三。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/play-assets/screenshots"
OUT = ROOT / "docs/play-assets/store-ready"
FONTS = Path(__file__).parent / "fonts"
REVIEW = Path(__file__).parent / "_review"  # 缩略对照图放这里，不混进待上传目录

W, H = 1080, 1920  # Play 要求长宽比 ≤ 2:1；原始截屏 1080x2400=2.22 会被拒
# 画布比 App 自身的暖纸色 #F3EDDF 略深：截屏内容大面积就是 #F3EDDF，同色的话
# 手机卡片会和背景融成一片，只剩投影撑轮廓。
BG = (0xE9, 0xDF, 0xC6)
INK = (0x2C, 0x23, 0x16)
SUB = (0x5A, 0x4B, 0x34)
ACCENT = (0xA1, 0x4E, 0x28)

MIN_HEAD_SIZE = 92
HEAD_SIZE = 104  # 15 条大字实测后取的统一最大字号（最宽的两行版占画布 ~86%）
SUB_SIZE = 46
MAX_TEXT_W = 960
ZONE_H = 430  # 上方留给大字
CARD_TOP = ZONE_H
CROP_TOP = 100  # 裁掉状态栏（里面有开发者自己的通知图标）
SRC_H = 2400
SAFE_BOTTOM = 2352  # 再往下是原截屏的黑色导航条 + 手势条，不能入镜
MAX_CARD_W = 860
RADIUS = 44

# key 决定文件名；bottom = 该屏「必须入镜」的原图最低行（决定缩放）
SLIDES = {
    "en-US": [
        dict(
            key="scan-and-listen", src="EN_02_scan", head="SCAN & LISTEN", bottom=2350
        ),
        dict(
            key="sourced-never-invented",
            src="EN_03_result",
            head="SOURCED, NEVER INVENTED",
            bottom=1900,
        ),
        dict(
            key="explore-freely",
            src="EN_01_home",
            head="EXPLORE FREELY",
            sub="No account. 5 free scans.",
            bottom=1900,
        ),
        dict(
            key="guides-in-10-languages",
            src="EN_10_languages",
            head="GUIDES IN 10 LANGUAGES",
            bottom=2095,
        ),
        dict(
            key="in-depth-guide",
            src="EN_06_indepth",
            head="IN-DEPTH GUIDE",
            bottom=1900,
        ),
        dict(
            key="rich-art-collection",
            src="EN_05_collection",
            head="RICH ART COLLECTION",
            bottom=1900,
        ),
        dict(
            key="no-rental-no-queue",
            src="EN_09_audio",
            head="NO RENTAL, NO QUEUE",
            special="norental",
        ),
        dict(
            key="paris-city-pass",
            src="EN_07_pass",
            head="PARIS CITY PASS",
            sub="Louvre · Orsay · Orangerie · Petit Palais",
            bottom=2185,
        ),
    ],
    "fr-FR": [
        dict(
            key="scannez-et-ecoutez",
            src="FR_02_scan",
            head="SCANNEZ & ÉCOUTEZ",
            bottom=2350,
        ),
        dict(
            key="source-jamais-invente",
            src="FR_03_result",
            head="SOURCÉ, JAMAIS INVENTÉ",
            bottom=1900,
        ),
        dict(
            key="explorez-librement",
            src="FR_01_home",
            head="EXPLOREZ LIBREMENT",
            sub="Sans compte. 5 scans offerts.",
            bottom=1900,
        ),
        dict(
            key="guides-approfondis",
            src="FR_06_indepth",
            head="GUIDES APPROFONDIS",
            bottom=1900,
        ),
        dict(
            key="des-milliers-d-oeuvres",
            src="FR_05_collection",
            head="DES MILLIERS D’ŒUVRES",
            bottom=1900,
        ),
        dict(
            key="ni-location-ni-file-d-attente",
            src="FR_09_audio",
            head="NI LOCATION, NI FILE D’ATTENTE",
            special="norental",
        ),
        dict(
            key="pass-ville-paris",
            src="FR_07_pass",
            head="PASS VILLE PARIS",
            sub="Louvre · Orsay · Orangerie · Petit Palais",
            bottom=2185,
        ),
    ],
    "zh-CN": [
        dict(
            key="scan-and-listen",
            src="ZH_02_scan",
            head="拍照识别，即听讲解",
            bottom=2350,
        ),
        dict(
            key="sourced-never-invented",
            src="ZH_03_result",
            head="来源可查，绝不编造",
            bottom=1900,
        ),
        dict(
            key="explore-freely",
            src="ZH_01_home",
            head="自由探索",
            sub="无需注册 · 5 次免费扫描",
            bottom=1900,
        ),
        dict(
            key="in-depth-guide",
            src="ZH_06_indepth",
            head="深度中文讲解",
            bottom=1900,
        ),
        dict(
            key="thousands-of-works",
            src="ZH_05_collection",
            head="数千件作品",
            bottom=1900,
        ),
        dict(
            key="no-rental-no-queue",
            src="ZH_09_audio",
            head="不租讲解器，不排队",
            special="norental",
        ),
        dict(
            key="paris-7-day-pass",
            src="ZH_07_pass",
            head="巴黎 7 日通票",
            sub="卢浮宫 · 奥赛 · 橘园 · 小皇宫",
            bottom=2185,
        ),
    ],
}


# 中文用 Noto SC 子集（完整字体 8–12MB；子集只含 SLIDES 用到的字，见 fonts/README.md）
HEAD_FONT = {"zh-CN": "NotoSerifSC-Bold-subset.otf"}
SUB_FONT = {"zh-CN": "NotoSansSC-Regular-subset.otf"}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def comma_split(text: str, f: ImageFont.FreeTypeFont) -> list[str] | None:
    """在逗号处断成两行（语义完整）；放不下返回 None。"""
    words = text.split(" ")
    for i in range(1, len(words)):
        if words[i - 1].endswith(","):
            a, b = " ".join(words[:i]), " ".join(words[i:])
            if max(f.getlength(a), f.getlength(b)) <= MAX_TEXT_W:
                return [a, b]
    return None


def balanced_split(text: str, f: ImageFont.FreeTypeFont) -> list[str]:
    words = text.split(" ")
    splits = [
        (max(f.getlength(" ".join(words[:i])), f.getlength(" ".join(words[i:]))), i)
        for i in range(1, len(words))
    ]
    width, i = min(splits)
    if width > MAX_TEXT_W:
        raise SystemExit(f"大字放不下（{width:.0f}px > {MAX_TEXT_W}px）：{text}")
    return [" ".join(words[:i]), " ".join(words[i:])]


def layout_head(
    text: str, lang: str = "en-US"
) -> tuple[list[str], ImageFont.FreeTypeFont]:
    """能一行就一行；有逗号就在逗号处断（必要时把字号略缩，最低 92）；否则均衡两行。

    只按宽度均衡会把 "NI LOCATION, NI / FILE D’ATTENTE" 断在 NI 后面，撕开语义；
    而 "NI FILE D’ATTENTE" 单行在 104px 下占画布 94%，故此处宁可缩小 ~6% 也不撕开。
    """
    head_font = HEAD_FONT.get(lang, "NotoSerif-Bold.ttf")
    hf = font(head_font, HEAD_SIZE)
    if hf.getlength(text) <= MAX_TEXT_W:
        return [text], hf
    if "," in text:
        for size in range(HEAD_SIZE, MIN_HEAD_SIZE - 1, -2):
            f = font(head_font, size)
            lines = comma_split(text, f)
            if lines:
                return lines, f
    return balanced_split(text, hf), hf


def draw_text_block(
    canvas: Image.Image, head: str, sub: str | None, lang: str = "en-US"
) -> None:
    d = ImageDraw.Draw(canvas)
    sf = font(SUB_FONT.get(lang, "NotoSans-Regular.ttf"), SUB_SIZE)
    lines, hf = layout_head(head, lang)
    if hf.size != HEAD_SIZE:
        print(f"    ↳ 「{head}」字号 {hf.size}px（为保住逗号处断行）")
    lh = round(hf.size * 1.14)
    sub_gap, sub_lh = 26, round(SUB_SIZE * 1.2)
    block = len(lines) * lh + (sub_gap + sub_lh if sub else 0)
    y = ZONE_H / 2 - block / 2
    for ln in lines:
        d.text((W / 2, y), ln, font=hf, fill=INK, anchor="ma")
        y += lh
    if sub:
        if sf.getlength(sub) > MAX_TEXT_W:
            raise SystemExit(f"第二行放不下：{sub}")
        d.text((W / 2, y + sub_gap), sub, font=sf, fill=SUB, anchor="ma")


def rounded_mask(size: tuple[int, int], r: int) -> Image.Image:
    """只圆上方两角；下方直角——卡片从画布底部出血，圆角露出来就像卡片在画面内结束。"""
    s = 3  # 超采样抗锯齿
    m = Image.new("L", (size[0] * s, size[1] * s), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size[0] * s - 1, size[1] * s - 1], r * s, fill=255)
    d.rectangle([0, size[1] * s // 2, size[0] * s - 1, size[1] * s - 1], fill=255)
    return m.resize(size, Image.LANCZOS)


def paste_card(canvas: Image.Image, shot: Image.Image, x: int, y: int) -> None:
    """圆角 + 极淡投影。shot 已是缩放、裁好的成品。"""
    mask = rounded_mask(shot.size, RADIUS)
    pad = 80
    sh = Image.new("RGBA", (shot.width + pad * 2, shot.height + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [pad, pad, pad + shot.width, pad + shot.height], RADIUS, fill=(44, 35, 22, 78)
    )
    sh = sh.filter(ImageFilter.GaussianBlur(24))
    canvas.paste(sh, (x - pad, y - pad + 12), sh)
    canvas.paste(shot, (x, y), mask)


def load_shot(lang: str, name: str) -> Image.Image:
    im = Image.open(SRC / lang / f"screenshot_{name}.jpg").convert("RGB")
    if im.size != (1080, SRC_H):
        raise SystemExit(f"{name} 不是 1080x{SRC_H}：{im.size}")
    return im


def standard_card(shot: Image.Image, bottom: int) -> tuple[Image.Image, int]:
    avail = H - CARD_TOP
    scale = min(MAX_CARD_W / 1080, avail / (bottom - CROP_TOP))
    rows = min(SAFE_BOTTOM, CROP_TOP + avail / scale)  # 下方允许出血
    crop = shot.crop((0, CROP_TOP, 1080, round(rows)))
    card = crop.resize((round(1080 * scale), round(crop.height * scale)), Image.LANCZOS)
    return card, (W - card.width) // 2


def draw_rental_device(height: int) -> Image.Image:
    """通用造型的租借讲解器：挂绳 + 听筒 + 数字键盘。纯几何，不复刻任何真实设备。"""
    s = 2  # 超采样
    cw, ch = 400 * s, 1040 * s
    im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    body, edge, dark = (204, 195, 178, 255), (156, 146, 128, 255), (176, 166, 148, 255)

    def rr(box, r, **kw):
        d.rounded_rectangle([v * s for v in box], r * s, **kw)

    d.arc([v * s for v in (120, 0, 280, 240)], 180, 360, fill=edge, width=9 * s)  # 挂绳
    rr((100, 160, 300, 940), 62, fill=body, outline=edge, width=7 * s)  # 机身
    rr((150, 215, 250, 240), 12, fill=dark)  # 扬声槽
    rr(
        (138, 290, 262, 400), 14, fill=(226, 220, 205, 255), outline=edge, width=5 * s
    )  # 屏幕
    for row in range(4):  # 键盘 3x4
        for col in range(3):
            cx, cy = 150 + col * 50, 500 + row * 92
            d.ellipse(
                [(cx - 21) * s, (cy - 21) * s, (cx + 21) * s, (cy + 21) * s], fill=dark
            )
    im = im.resize((cw // s, ch // s), Image.LANCZOS)
    return im.resize((round(im.width * height / im.height), height), Image.LANCZOS)


def norental_slide(canvas: Image.Image, shot: Image.Image) -> None:
    """主体=讲解播放中的手机；配角=小、去饱和、带删除线的通用讲解器。不做左右分屏。"""
    top = CARD_TOP + 10
    avail = H - top
    scale = 0.66  # 够大才能从底部出血；再大讲解器就没地方放了
    crop = shot.crop(
        (0, CROP_TOP, 1080, round(min(SAFE_BOTTOM, CROP_TOP + avail / scale)))
    )
    card = crop.resize((round(1080 * scale), round(crop.height * scale)), Image.LANCZOS)
    paste_card(canvas, card, W - card.width - 40, top)

    dev = draw_rental_device(460)
    dev = dev.rotate(9, expand=True, resample=Image.BICUBIC)
    a = dev.getchannel("A").point(lambda v: int(v * 0.62))  # 淡化
    dev.putalpha(a)
    dx, dy = 40, CARD_TOP + 420
    canvas.paste(dev, (dx, dy), dev)

    # 克制的删除线：一道斜线压过讲解器
    s = 3
    layer = Image.new("RGBA", (dev.width * s, dev.height * s), (0, 0, 0, 0))
    ImageDraw.Draw(layer).line(
        [
            (0.10 * dev.width * s, 0.86 * dev.height * s),
            (0.90 * dev.width * s, 0.14 * dev.height * s),
        ],
        fill=ACCENT + (215,),
        width=15 * s,
    )
    layer = layer.resize(dev.size, Image.LANCZOS)
    canvas.paste(layer, (dx, dy), layer)


def compose(lang: str, spec: dict) -> Image.Image:
    canvas = Image.new("RGB", (W, H), BG)
    draw_text_block(canvas, spec["head"], spec.get("sub"), lang)
    shot = load_shot(lang, spec["src"])
    if spec.get("special") == "norental":
        norental_slide(canvas, shot)
    else:
        card, x = standard_card(shot, spec["bottom"])
        paste_card(canvas, card, x, CARD_TOP)
    return canvas


def main() -> None:
    contact = "--contact" in sys.argv
    made: dict[str, list[Path]] = {}
    for lang, slides in SLIDES.items():
        (OUT / lang).mkdir(parents=True, exist_ok=True)
        for old in (OUT / lang).glob("*.png"):
            old.unlink()  # 幻灯片增减时不留过期文件
        for n, spec in enumerate(slides, 1):
            p = OUT / lang / f"{n:02d}_{spec['key']}.png"
            compose(lang, spec).save(p, "PNG", optimize=True)
            made.setdefault(lang, []).append(p)
            print(f"  {p.relative_to(ROOT)}  {p.stat().st_size // 1024}KB")
    if contact:
        tw = 216
        th = round(H * tw / W)
        for lang, files in made.items():
            cols = 4
            rows = -(-len(files) // cols)
            sheet = Image.new("RGB", (cols * tw, rows * th), (255, 255, 255))
            for i, f in enumerate(files):
                sheet.paste(
                    Image.open(f).resize((tw, th), Image.LANCZOS),
                    ((i % cols) * tw, (i // cols) * th),
                )
            REVIEW.mkdir(exist_ok=True)
            sheet.save(REVIEW / f"contact_{lang}.png")
        print("  已输出缩略对照图 tools/aso/_review/contact_*.png")


if __name__ == "__main__":
    main()
