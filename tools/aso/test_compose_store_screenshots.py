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

sys.path.insert(0, str(Path(__file__).parent))

import compose_store_screenshots as c  # noqa: E402


def test_headlines_fit_and_break_at_comma():
    for slides in c.SLIDES.values():
        for s in slides:
            lines, f = c.layout_head(s["head"])
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
