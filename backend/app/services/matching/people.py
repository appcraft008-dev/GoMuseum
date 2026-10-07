"""是不是同一个人(署名判同/识别作者加分/编号+作者直判共用)。

prod 10-07 实测:署名与作者名只差词序/逗号/生卒年/修饰词时整串比较认不出(571 条);
另有两条否决先于判同——
- 摄影/复制归属(reproduced by …)是 CC 要求的署名,哪怕前面写着画家名也要显示;
- 两边代际修饰不同(the Elder vs the Younger)是父子两个人(目录里 8 对)。"""

from __future__ import annotations

import re

from app.services.matching.normalize import normalize

_PHOTO = re.compile(
    r"reproduced by|pho+to|clich[eé]|©|\(c\)|\brmn\b|uploaded by|derivative work",
    re.IGNORECASE,
)
_PAREN = re.compile(r"\([^()]*\)")
_SPLIT = re.compile(r"\s*(?:/|;|&amp;|&|\band\b|\bet\b)\s*", re.IGNORECASE)
_QUAL = {
    "probably", "possibly", "attributed", "to", "after", "copy", "of", "workshop",
    "circle", "school", "follower", "manner", "studio", "atelier", "d", "apres",
    "attribue", "a", "sculpteur", "peintre", "painter", "sculptor", "the", "le", "l",
}  # fmt: skip
_GEN = {
    "elder": "elder", "ancien": "elder", "pere": "elder", "senior": "elder",
    "younger": "younger", "jeune": "younger", "fils": "younger", "junior": "younger",
}  # fmt: skip


def _words(s: str) -> list[str]:
    return normalize(s).split()


def _generation(s: str) -> set[str]:
    return {_GEN[w] for w in _words(s) if w in _GEN}


def _person(s: str) -> frozenset[str]:
    return frozenset(
        w for w in _words(s) if w not in _QUAL and w not in _GEN and not w.isdigit()
    )


def _people(s: str) -> list[frozenset[str]]:
    """一个署名串 → 每个人的词集合(先剥括号里的生卒年/出生地),外加整串一份。"""
    while _PAREN.search(s):
        s = _PAREN.sub(" ", s)
    parts = [_person(p) for p in _SPLIT.split(s)]
    whole = frozenset(w for p in parts for w in p)
    return [p for p in parts if p] + ([whole] if whole else [])


def same_person(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    if a.strip().casefold() == b.strip().casefold():
        return True
    ga, gb = _generation(a), _generation(b)
    if ga and gb and ga != gb:
        return False
    pb = _people(b)
    return any(x == y for x in _people(a) for y in pb)


def is_artist_credit(credit: str, aliases) -> bool:
    """署名是不是作者本人(是 → 不显示)。旧的整串相等一路保留在最前。"""
    norm = credit.strip().casefold()
    if any(norm == a.strip().casefold() for a in aliases if a):
        return True
    if _PHOTO.search(credit):
        return False
    lines = [ln for ln in credit.splitlines() if ln.strip()]
    if len(lines) > 1:
        # Commons 多字段(作者一行 + 上传者/摄影者一行,如 "Emmanuel Frémiet\nSiren-Com"):
        # 每一行都是作者才算;有一行不是 → 那行可能是 CC 署名,整条显示
        return all(is_artist_credit(ln, aliases) for ln in lines)
    return any(same_person(credit, a) for a in aliases if a)
