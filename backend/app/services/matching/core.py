"""识别文字链的判定:候选名/墙签行 → [(qid, score)](只含过门槛的)+ 原始前 5(诊断)。

门槛来自 10-07 评测(spec §2.1):对半切,一半网格调参、另一半留出复验——
0.75/0.9 在留出集:标题对 97%/100%(排第1/进前3)、半标题 89%/94%、垃圾输入 0% 出候选、
库外名作 20% 出候选。作者加分参与排序不封顶(原 min(…,1.0) 让作者打破不了同名并列)。"""

from __future__ import annotations

from rapidfuzz import fuzz

from app.services.matching.index import core_for
from app.services.matching.normalize import normalize, tokens
from app.services.matching.people import same_person

ACCEPT_WITH_ARTIST = 0.75
ACCEPT_TITLE_ONLY = 0.9
ARTIST_BONUS = 0.1
REVSUB_MIN = 8  # 反向子串:目录名 ≥8 字符整串出现在墙签里
REVSUB_SCORE = 0.8  # 只有作者也对上才够门槛
_PER_QUERY = 200


def title_sim(q: str, n: str) -> float:
    """ratio;查询比库名短(且 ≥40%)时另取 0.95×partial_ratio。只单向——
    反过来短库名(「Composition」)会吃进长查询(10-07 原型误报来源)。"""
    r = fuzz.ratio(q, n)
    if len(n) * 0.4 <= len(q) <= len(n):
        r = max(r, 0.95 * fuzz.partial_ratio(q, n))
    return r / 100


def recognize(
    index,
    queries,
    label_lines,
    artist_hints=None,
    limit=5,
    label_lines_inv_only=False,
):
    """→ (过门槛的 [(qid, score)] 降序, 原始前 5 [[qid, score, 作者对上]])。"""
    from app.services.recognition.matcher import _inv_probes

    queries = [q for q in queries if q]
    label_lines = [x for x in label_lines if x]
    fuzzy_src = queries if label_lines_inv_only else queries + label_lines
    probes = [p for p in (normalize(q) for q in fuzzy_src) if p]
    inv = _inv_probes(queries + label_lines)
    ocr_norm = "" if label_lines_inv_only else normalize(" ".join(label_lines))
    hints = [h for h in (artist_hints or []) if h]
    if not label_lines_inv_only:
        # 墙签里单独成行的作者名(「Henri-Edmond Cross」)同样是作者证据;整行长句命中不了
        # same_person(词集合要相等),长句靠下面「作者名是墙签原文子串」那一路
        hints += label_lines
    core, allowed = core_for(index)

    cand: dict[int, float] = {}
    for p in probes:
        for i, _ in core.recall(tokens(p), _PER_QUERY, allowed):
            e = core.entries[i]
            s = max((title_sim(p, n) for n in e["names"]), default=0.0)
            if ocr_norm and any(
                len(n) >= REVSUB_MIN and n in ocr_norm for n in e["names"]
            ):
                s = max(s, REVSUB_SCORE)
            cand[i] = max(cand.get(i, 0.0), s)
    if inv:
        for i, e in enumerate(core.entries):
            if (allowed is None or i in allowed) and e.get("inv") in inv:
                cand[i] = 1.0

    rows = []
    for i, s in cand.items():
        e = core.entries[i]
        ok = any(same_person(h, a) for h in hints for a in e["artists"]) or bool(
            ocr_norm and any(len(a) >= 6 and a in ocr_norm for a in e["artists"])
        )
        rows.append((s + ARTIST_BONUS * ok, s, ok, e["qid"]))
    rows.sort(key=lambda r: -r[0])

    raw = [[q, round(min(k, 1.0), 3), ok] for k, _, ok, q in rows[:5]]
    best: dict[str, float] = {}
    for k, s, ok, q in rows:
        if s >= 1.0 or s >= (ACCEPT_WITH_ARTIST if ok else ACCEPT_TITLE_ONLY):
            best.setdefault(q, min(k, 1.0))
    return list(best.items())[:limit], raw
