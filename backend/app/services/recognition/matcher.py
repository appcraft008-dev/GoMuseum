"""匹配层(识别的不变核心;P2 换 CLIP 引擎也不动它):
候选名/墙签行 → 该馆目录多语模糊匹配 → [(qid, score)] 降序。
R1 接地:身份只可能来自这里匹配到的真实目录记录。
打分与判定在 matching.core(倒排召回 + rapidfuzz);索引复用搜索的全局索引(见 build_index)。"""

from __future__ import annotations

import re

from app.services.matching.normalize import (  # noqa: F401  再导出
    normalize,
    normalize_inv,
)
from app.services.matching.people import same_person, surname_seen

HIGH = 0.85  # ≥ 直开讲解页;真实数据校准前的初值
LOW = 0.5  # < 未收录;[LOW, HIGH) 出确认卡


_INV_MIN = 3  # 归一化后长度 <3 不做编号匹配(防误伤)
# 从整段 OCR 抽馆藏号样式 token(≥2 字母前缀 + 至多 3 段数字)。脏 OCR 把标题/号/尺寸
# 挤一行时,整行 normalize_inv 抠不出号,靠此正则补(实测 0.55→1.0)。数字段有界,避免
# 贪婪吞掉紧随的尺寸位;抽号前先剥"74x94cm"类尺寸,防污染。
# 卢浮墙签印「INV. 1186」「R.F. 2372」「INV. 595 ter」(10-07 真机):字母间可带点,可带 bis/ter。
_DIM = re.compile(r"\d+\s*[x×]\s*\d+\s*(?:cm|mm|in)?", re.IGNORECASE)
_INV_TOKEN = re.compile(
    r"\b(?:[A-Za-z]\.?){2,4}\s?\d{1,5}(?:[\s\-]\d{1,4}){0,2}(?:\s(?:bis|ter)\b)?"
)


def build_index(db, museum_id) -> list[dict]:
    """馆目录 → [{"qid","names","artists","inv","museum_id",...}](归一化)。
    museum_id=None → 全部馆。

    直接复用搜索的全局索引(`search.inprocess.build_search_index`):两边要的字段完全一样
    (多语标题/作者名/馆藏号,同一套 normalize),而搜索那份已经只读必要列、过期后台重建、
    启动时预热。原先这里自建一份:全列加载 2.7 万件冷建 13s,每 600s 过期在用户请求里
    同步重建(prod 2026-10-06 实测)。"""
    from app.services.search.inprocess import build_search_index

    return build_search_index(db, museum_id)


def _inv_probes(raw_probes: list[str]) -> set[str]:
    """馆藏号精确匹配探针(候选名+墙签行,不含 artist_hints;归一化后长度≥3 才算)。"""
    inv = {i for i in (normalize_inv(q) for q in raw_probes) if len(i) >= _INV_MIN}
    # 脏 OCR 补抽:整行归一化抠不出号时,从全文正则抽馆藏号 token(先剥尺寸防污染)
    for tok in _INV_TOKEN.findall(_DIM.sub(" ", " ".join(raw_probes))):
        t = normalize_inv(tok)
        if len(t) >= _INV_MIN:
            inv.add(t)
    return inv


def inv_artist_hit(
    index: list[dict], texts: list[str], artist_hints: list[str] | None = None
) -> str | None:
    """馆藏号精确命中 + 该件作者也对上(出现在原文里或 AI 摘出的作者)→ 唯一 qid,否则 None。
    文字链本不直判(同名撞车);编号+作者双重吻合足以排除。作者只认原文/AI 摘出两路——
    AI 会张冠李戴(10-06 把 Cross 写成 Signac),原文里印着的名字更可靠。
    同号多件(RF 编号跨馆共用,prod 765 组)→ 不直判。
    编号已精确相等,作者这一步只防撞号,姓对上即可(名的拼法常不同:Gaspard/Gaspar)。"""
    raw = [t for t in texts if t]
    inv = _inv_probes(raw)
    if not inv:
        return None
    text_norm = normalize(" ".join(raw))
    hints = [a for a in (artist_hints or []) if a]  # same_person 自己归一化
    words = set(normalize(" ".join(raw + hints)).split())
    hits = set()
    for e in index:
        if not (e.get("inv") and e["inv"] in inv):
            continue
        if surname_seen(e["artists"], words) or any(
            an and (an in text_norm or any(same_person(h, an) for h in hints))
            for an in e["artists"]
        ):
            hits.add(e["qid"])
    return hits.pop() if len(hits) == 1 else None


def match_with_trace(
    index: list[dict],
    queries: list[str],
    label_lines: list[str],
    artist_hints: list[str] | None = None,
    limit: int = 5,
    label_lines_inv_only: bool = False,
):
    """→ (过门槛的 [(qid, score)], 原始前 5 [[qid, score, 作者对上]])。判定见 matching.core
    (spec docs/superpowers/specs/2026-10-07-matching-core-design.md §3.3)。"""
    from app.services.matching.core import recognize

    return recognize(
        index, queries, label_lines, artist_hints, limit, label_lines_inv_only
    )


def match(
    index: list[dict],
    queries: list[str],
    label_lines: list[str],
    artist_hints: list[str] | None = None,
    limit: int = 5,
    label_lines_inv_only: bool = False,
) -> list:
    """查询串(候选题名)+墙签行 → 过门槛的前 limit 个 [(qid, score)] 降序去重。
    ⚠️ artist_hints 只参与作者判定、绝不当标题探针——否则"以画家为题"的肖像画
    (如巴齐耶《奥古斯特·雷诺阿像》)会被候选作者名精确劫持(staging 真实误配)。
    label_lines_inv_only=True:墙签行只用来抽馆藏号,不做模糊/反向子串(墙签模式已摘出标题时;
    作者行会劫持同名肖像——2026-10-06《Henri Edmond Cross》像与《晚风》并列)。"""
    return match_with_trace(
        index, queries, label_lines, artist_hints, limit, label_lines_inv_only
    )[0]
