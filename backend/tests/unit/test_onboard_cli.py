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
