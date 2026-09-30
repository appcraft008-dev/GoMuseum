"""正文里带称号的人名(Seneca the Younger / Charles the Bold)→ 目标语言的权威译名。

翻译模型不认识这些称号的规范译法,只会猜:prod 实测「年轻的塞内卡」「查理·布尔德」
「大帝萨尔贡」「세네카 젊은이」。prompt 里加规则 A/B 反而更糟(Charles the Bold→
「查理大帝」= 换了个人);gpt-4o 单独翻名字韩语仍大面积错、小勃鲁盖尔在「小/老」间摇摆。
→ 不靠模型记忆:按英文全名在 Wikidata 精确匹配到实体,取它的各语官方标签,
当规范名注入翻译(与标题/作者/馆名同一机制)。查不到/出错 → 不注入,行为同改动前。
ponytail: 标签有时丢称号(ja「シャルル」)—— 那是少了信息,不是错信息,接受。
"""

from __future__ import annotations

import re
from functools import lru_cache

_BY_NAME = re.compile(
    r"\b((?:[A-Z][\w'’\-]+ ){1,4})the "
    r"(Younger|Elder|Great|Bold|Good|Pious|Fair|Wise|Magnificent|Conqueror)\b"
)


def find(text: str) -> list[str]:
    """文中候选全名(去重保序)。句首大写词会被一起抓进来,resolve 时逐级去掉前缀。"""
    out: list[str] = []
    for m in _BY_NAME.finditer(text or ""):
        name = f"{m.group(1)}the {m.group(2)}"
        if name not in out:
            out.append(name)
    return out


def _wd_search(name: str) -> list[dict]:
    import requests

    from app.services.enrichment.sources import wikidata as _wd

    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "type": "item",
            "limit": 5,
            "format": "json",
        },
        headers={"User-Agent": _wd.USER_AGENT},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("search", [])


@lru_cache(maxsize=512)
def _qid(name: str) -> str | None:
    """英文全名精确等于某实体的标签或别名才算命中(不取模糊的第一条)。"""
    for hit in _wd_search(name):
        match = hit.get("match") or {}
        if match.get("type") in ("label", "alias") and (
            match.get("text", "").lower() == name.lower()
        ):
            return hit["id"]
    return None


@lru_cache(maxsize=2048)
def _label(qid: str, lang: str) -> str | None:
    from app.services.enrichment.material import fetch_wikidata_labels

    return fetch_wikidata_labels(qid, [lang]).get(lang)


def resolve(name: str, lang: str) -> tuple[str, str] | None:
    """「In Seneca the Younger」这类带句首词的候选:从长到短试,第一个精确命中的算。
    返回 (命中的英文名, 译名)。"""
    head, _, tail = name.rpartition(" the ")
    words = head.split()
    for i in range(len(words)):
        cand = " ".join(words[i:]) + " the " + tail
        qid = _qid(cand)
        if qid:
            label = _label(qid, lang)
            return (cand, label) if label else None
    return None


# 只管实测出错的语言。欧洲语言有同构称号(le Jeune / der Jüngere / el Joven),
# 模型本就译得对;而 Wikidata 的 fr 标签反倒常丢称号(Q2054 fr=「Sénèque」)。
LANGS = {"zh", "zh-hant", "ja", "ko"}


def glossary(text: str, lang: str) -> dict[str, str]:
    """{英文原名: 目标语言权威译名}。网络/解析任何失败都只是少一条,不影响翻译本身。"""
    out: dict[str, str] = {}
    if lang not in LANGS:
        return out
    for name in find(text):
        try:
            hit = resolve(name, lang)
        except Exception:
            continue
        if hit:
            out[hit[0]] = hit[1]
    # 两个人拿到同一个译名(ja 老/小勃鲁盖尔都是「ピーテル・ブリューゲル」)→ 注入会把
    # 两人写成一个人,不如不给,让模型自己区分。
    labels = list(out.values())
    return {en: loc for en, loc in out.items() if labels.count(loc) == 1}
