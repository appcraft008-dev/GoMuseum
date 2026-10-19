#!/usr/bin/env python3
"""韩文 UI 文案按词断行（CSS word-break: keep-all 的效果）。

Flutter 没有 keep-all：韩文默认在任意两个音节之间都可断行（"미|술관에서"）。
在同一个词内部、相邻的谚文/字母/数字之间插入 U+2060（WORD JOINER，不可见、
禁止断行），断行就只会落在空格处。

改了 app_ko.arb 后跑一次（幂等）：
    python3 scripts/ko_keep_all.py
test/i18n/ko_keep_all_test.dart 会在漏跑时变红。
"""
import json
import re
from pathlib import Path

ARB = Path(__file__).resolve().parent.parent / "lib/l10n/app_ko.arb"
WJ = "\u2060"
_H = "\uac00-\ud7a3"
# 占位符两侧也连上：{count}일 渲染成 "7일"，不连会断成 "7|일"。
_JOIN = re.compile(rf"(?<=[{_H}])(?=[{_H}0-9A-Za-z{{])|(?<=[0-9A-Za-z}}])(?=[{_H}])")


def keep_all(s: str) -> str:
    return _JOIN.sub(WJ, s)


def main() -> None:
    data = json.loads(ARB.read_text(encoding="utf-8"))
    for k, v in data.items():
        if not k.startswith("@") and isinstance(v, str):
            data[k] = keep_all(v)
    ARB.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
