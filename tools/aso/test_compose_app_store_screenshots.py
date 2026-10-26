"""compose_app_store_screenshots.py 的单测。

运行（仓库根目录）：
  cd backend && poetry run pytest ../tools/aso/test_compose_app_store_screenshots.py --no-cov
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import compose_app_store_screenshots as a  # noqa: E402
import compose_store_screenshots as c  # noqa: E402


def test_every_slide_meets_app_store_spec():
    with a.app_store():
        for lang, slides in c.SLIDES.items():
            assert 1 <= len(slides) <= 10, lang  # App Store：每种设备 1–10 张
            for s in slides:
                lines, f = c.layout_head(s["head"], lang)
                assert len(lines) <= 2, s["head"]
                im = c.compose(lang, s)
                assert im.size == (1320, 2868), s["key"]  # 6.9 寸
                assert im.mode == "RGB", s["key"]  # 无 alpha


def test_play_module_restored_after_use():
    """切规格是临时的：用完 Play 版必须还是 1080x1920，否则同进程跑的 Play 测试会出错图。"""
    with a.app_store():
        pass
    assert (c.W, c.H) == (1080, 1920)
    assert c.load_shot is not a.load_shot
    assert c.compose("en-US", c.SLIDES["en-US"][0]).size == (1080, 1920)
