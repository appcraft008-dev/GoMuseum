"""Play 商店图标 V1（加粗取景框角标）+ 三语置顶大图同步换图标。

背景：Console 里的图标取景框角标偏大偏淡（角标 vs 底色对比度 1.72:1，48px 下不可见）。
V1 = 同一个陶土红柱廊 + 奶油底，角标改陶土红、加粗、收紧。桌面自适应图标本来就没有角标，
所以只改商店侧素材，不需要发包。

置顶大图只重画左侧图标区（x<500），文字区原样保留，所以三语文字与旧稿逐像素一致。

用法（仓库根目录）：  cd backend && poetry run python ../tools/aso/make_icon_v1_and_feature_graphic.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
FOREGROUND = ROOT / "frontend/gomuseum_app/assets/icon/app_icon_foreground.png"
ICON_OUT = ROOT / "docs/play-assets/icon-candidates/icon_512_V1_cream_bold_brackets.png"
FG_DIR = ROOT / "docs/play-assets/feature-graphic"

CREAM = (0xF3, 0xED, 0xDF)
TERRA = (0xA1, 0x4E, 0x28)
K = 8  # 超采样倍数


def icon(size: int) -> Image.Image:
    """奶油底 + 陶土红柱廊 + 陶土红加粗角标（inset 64 / arm 84 / stroke 18，按 512 基准）。"""
    n = size * K
    im = Image.new("RGB", (n, n), CREAM)
    alpha = Image.open(FOREGROUND).convert("RGBA").resize((n, n), Image.LANCZOS)
    im.paste(Image.new("RGB", (n, n), TERRA), (0, 0), alpha.getchannel("A"))
    d, u = ImageDraw.Draw(im), n / 512
    i, arm, w = 64 * u, 84 * u, 18 * u
    lo = n - i
    for x, y, sx, sy in ((i, i, 1, 1), (lo, i, -1, 1), (i, lo, 1, -1), (lo, lo, -1, -1)):
        d.rectangle([min(x, x + sx * arm), min(y, y + sy * w), max(x, x + sx * arm), max(y, y + sy * w)], fill=TERRA)
        d.rectangle([min(x, x + sx * w), min(y, y + sy * arm), max(x, x + sx * w), max(y, y + sy * arm)], fill=TERRA)
    return im.resize((size, size), Image.LANCZOS)


def feature_graphic(path: Path) -> None:
    fg = Image.open(path).convert("RGB")
    ImageDraw.Draw(fg).rectangle([0, 0, 499, fg.height], fill=CREAM)  # 文字从 x=516 起
    fg.paste(icon(440), (30, (fg.height - 440) // 2))  # 与旧稿同位置：West +30
    fg.save(path, optimize=True)


if __name__ == "__main__":
    icon(512).save(ICON_OUT, optimize=True)
    for lang in ("en-US", "fr-FR", "zh-CN"):
        feature_graphic(FG_DIR / f"{lang}.png")
    print("ok")
