"""把 iOS 模拟器真实截图合成为 App Store 6.9 寸商店图（1320x2868 PNG）。

排版函数全部复用 compose_store_screenshots（Play 版），这里只换三样：
  - 画布 1320x2868，版式常量（字号/字宽/标题区/卡宽/圆角）按 1320/1080 放大；
  - iOS 原截屏 1320x2868 先缩到 1080 宽再交给 Play 的函数（它们按 1080 宽写死）；
  - 每张都放整屏：iOS 画面比例更高，整屏缩放后刚好从标题区铺到画布底边。
    「不租讲解器」那张因此不画讲解器（卡片占满宽度，没地方放）。

大字/第二行文案与 Play 版逐字相同——中文字体是子集，换字要重新子集化。

原图来源：iPhone 17 Pro Max 模拟器（iOS 26.2）连 prod，状态栏固定 9:41；
第 1 张是「相册选图识别 → 结果页播放中」（模拟器没有相机）。

用法（在仓库根目录）：
  poetry -C backend run python tools/aso/compose_app_store_screenshots.py [--contact]
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

import compose_store_screenshots as c  # noqa: E402

W, H = 1320, 2868
K = W / 1080
SRC_H = round(2868 / K)  # 原截屏缩到 1080 宽后的高度
ROOT = c.ROOT / "docs/app-store-assets"

# Play 版的 src 名 → iOS 原图名；Play 的 scan 屏是取景框，iOS 用「选图识别后播放中」
IOS_SRC = {
    "02_scan": "02_scan_play",
    "03_result": "03_result",
    "01_home": "01_home",
    "10_languages": "10_languages",
    "06_indepth": "06_indepth",
    "05_collection": "05_collection",
    "09_audio": "09_audio",
    "07_pass": "07_pass",
}

SLIDES = {
    lang: [
        dict(
            key=s["key"],
            src=IOS_SRC[s["src"].split("_", 1)[1]],
            head=s["head"],
            **({"sub": s["sub"]} if "sub" in s else {}),
            bottom=SRC_H,
        )
        for s in slides
    ]
    for lang, slides in c.SLIDES.items()
}


def load_shot(lang: str, name: str) -> Image.Image:
    im = Image.open(ROOT / "screenshots" / lang / f"{name}.jpg").convert("RGB")
    if im.size != (W, H):
        raise SystemExit(f"{lang}/{name} 不是 {W}x{H}：{im.size}")
    return im.resize((1080, SRC_H), Image.LANCZOS)


@contextmanager
def app_store():
    """临时把 Play 模块切成 App Store 规格；退出即还原，不影响 Play 版及其测试。"""
    scaled = {
        n: round(getattr(c, n) * K)
        for n in (
            "HEAD_SIZE",
            "MIN_HEAD_SIZE",
            "SUB_SIZE",
            "MAX_TEXT_W",
            "ZONE_H",
            "CARD_TOP",
            "RADIUS",
        )
    }
    with mock.patch.multiple(
        c,
        W=W,
        H=H,
        SRC_H=SRC_H,
        CROP_TOP=152,  # 状态栏 + 灵动岛（62pt@3x=186px，缩到 1080 宽≈152）
        SAFE_BOTTOM=SRC_H,  # 模拟器截图不含 Home 条，整屏可用
        MAX_CARD_W=1160,  # 整屏铺满标题区以下所需宽度（≈88%）
        SLIDES=SLIDES,
        OUT=ROOT / "store-ready",
        REVIEW=Path(__file__).parent / "_review_app_store",
        load_shot=load_shot,
        **scaled,
    ):
        yield c


if __name__ == "__main__":
    with app_store():
        c.main()
