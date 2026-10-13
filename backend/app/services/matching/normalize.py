"""匹配核心的归一化与分词(搜索/识别/署名共用)。原在 recognition/matcher,matcher 再导出。"""

from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"[\s_]+")
_NONALNUM = re.compile(r"[^a-z0-9]+")
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def normalize(s: str) -> str:
    """小写/NFD 去音符/去标点/压空白(Théodore≈Theodore)。"""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = _PUNCT.sub(" ", s.lower())
    return _WS.sub(" ", s).strip()


def normalize_inv(s: str | None) -> str:
    """馆藏号归一化:小写 + 去所有非字母数字("RF 1668"→"rf1668")。空/None 安全。"""
    return _NONALNUM.sub("", (s or "").lower())


def is_cjk(tok: str) -> bool:
    return bool(_CJK.search(tok))


_CJK_GAP = re.compile(rf"(?<={_CJK.pattern}) (?={_CJK.pattern})")


def with_cjk_joined(names: set[str]) -> set[str]:
    """已归一化名集 + 中文字之间去空格的写法。中文译名的「·」归一化成空格
    (「列奥纳多 达 芬奇」),用户多半不打点(「达芬奇」)→ 两种写法都进索引。"""
    return names | {_CJK_GAP.sub("", n) for n in names}


def artist_keys(names: set[str]) -> set[str]:
    """作者名集再加去掉全部空格的写法:用户常把姓连写(「davinci」「vangogh」「vandyck」),
    原来只能靠拼错容错碰上、排在最低档。"""
    names = with_cjk_joined(names)
    return names | {n.replace(" ", "") for n in names}


def tokens(s: str) -> list[str]:
    """已归一化串 → 词。拉丁按空格;中日韩无空格,按二字组(单字保留)。"""
    out: list[str] = []
    for w in s.split():
        if is_cjk(w) and len(w) > 1:
            out += [w[i : i + 2] for i in range(len(w) - 1)]
        else:
            out.append(w)
    return out
