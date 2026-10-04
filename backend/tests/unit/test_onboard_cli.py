"""onboard CLI 参数接线冒烟(防 --retranslate-langs 类'加了却没注册'的 bug)。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_names_parser_accepts_all_flags():
    from scripts.onboard import build_parser

    ns = build_parser().parse_args(
        [
            "orsay",
            "names",
            "--target",
            "staging",
            "--langs",
            "zh",
            "--refresh-langs",
            "zh",
            "--retranslate-langs",
            "zh",
        ]
    )
    assert ns.command == "names"
    assert ns.retranslate_langs == "zh"
    assert ns.refresh_langs == "zh"


def test_images_step_tiles_wide_artworks(monkeypatch):
    """契约:宽幅作品切块挂在 images 物化之后,新馆/新件不靠人记得单独跑。"""
    import app.services.enrichment.materializer as mat
    import scripts.onboard as onboard
    import scripts.tile_wide_images as tw

    calls = []
    monkeypatch.setattr(onboard.settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(
        onboard, "SessionLocal", lambda: type("S", (), {"close": lambda s: None})()
    )
    monkeypatch.setattr(mat, "materialize_images", lambda db, slug, limit=None: {})
    monkeypatch.setattr(
        tw, "tile_museum", lambda slug, dry_run=False: calls.append(slug)
    )
    onboard.cmd_images("orangerie", None, "staging")
    assert calls == ["orangerie"]
