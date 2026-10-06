"""匹配层(识别的不变核心;P2 换 CLIP 引擎也不动它):
候选名/墙签行 → 该馆目录多语模糊匹配 → [(qid, score)] 降序。
R1 接地:身份只可能来自这里匹配到的真实目录记录。
stdlib difflib;索引复用搜索的全局索引(见 build_index)。"""

from __future__ import annotations

import heapq
import re
import unicodedata
from difflib import SequenceMatcher

HIGH = 0.85  # ≥ 直开讲解页;真实数据校准前的初值
LOW = 0.5  # < 未收录;[LOW, HIGH) 出确认卡


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"[\s_]+")
_NONALNUM = re.compile(r"[^a-z0-9]+")
_INV_MIN = 3  # 归一化后长度 <3 不做编号匹配(防误伤)
# 从整段 OCR 抽馆藏号样式 token(≥2 字母前缀 + 至多 3 段数字)。脏 OCR 把标题/号/尺寸
# 挤一行时,整行 normalize_inv 抠不出号,靠此正则补(实测 0.55→1.0)。数字段有界,避免
# 贪婪吞掉紧随的尺寸位;抽号前先剥"74x94cm"类尺寸,防污染。
_DIM = re.compile(r"\d+\s*[x×]\s*\d+\s*(?:cm|mm|in)?", re.IGNORECASE)
_INV_TOKEN = re.compile(r"[A-Za-z]{2,4}\s?\d{1,5}(?:[\s\-]\d{1,4}){0,2}")
_REVSUB_MIN = 8  # 反向子串:目录名归一化 ≥8 字符才算"出现在 OCR 里"(防短标题误报)
_REVSUB_SCORE = 0.7  # 反向子串命中分(≥LOW 出候选卡,<HIGH 不直判)
_ARTIST_BONUS = 0.1
_FLOOR = LOW - _ARTIST_BONUS - 1e-9  # 标题分 ≤ 此值,加满作者分也够不到 LOW


def normalize(s: str) -> str:
    """小写/NFD 去音符/去标点/压空白(Théodore≈Theodore)。"""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = _PUNCT.sub(" ", s.lower())
    return _WS.sub(" ", s).strip()


def normalize_inv(s: str) -> str:
    """馆藏号归一化:小写 + 去所有非字母数字("RF 1668"→"rf1668")。空/None 安全。"""
    return _NONALNUM.sub("", (s or "").lower())


def build_index(db, museum_id) -> list[dict]:
    """馆目录 → [{"qid","names","artists","inv","museum_id",...}](归一化)。
    museum_id=None → 全部馆。

    直接复用搜索的全局索引(`search.inprocess.build_search_index`):两边要的字段完全一样
    (多语标题/作者名/馆藏号,同一套 normalize),而搜索那份已经只读必要列、过期后台重建、
    启动时预热。原先这里自建一份:全列加载 2.7 万件冷建 13s,每 600s 过期在用户请求里
    同步重建(prod 2026-10-06 实测)。"""
    from app.services.search.inprocess import build_search_index

    return build_search_index(db, museum_id)


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _sim_above(a: str, b: str, floor: float) -> float:
    """ratio() 若 > floor 则返回之,否则 0.0。先用上界剪枝(结果与 ratio 完全一致):
    长度上界 2·min/(la+lb) 不构造对象;再 quick_ratio(字符多重集上界)。
    墙签模式整段 OCR 几十行 × 26 万个标题名,全量 ratio 在 prod 要十几分钟(2026-10-06 真机)。"""
    la, lb = len(a), len(b)
    if not la or not lb or 2 * min(la, lb) / (la + lb) <= floor:
        return 0.0
    sm = SequenceMatcher(None, a, b)
    if sm.quick_ratio() <= floor:
        return 0.0
    r = sm.ratio()
    return r if r > floor else 0.0


def match(
    index: list[dict],
    queries: list[str],
    label_lines: list[str],
    artist_hints: list[str] | None = None,
    limit: int = 5,
    label_lines_inv_only: bool = False,
) -> list:
    """查询串(候选题名)+墙签行 → 前 limit 个 [(qid, score)] 降序去重。
    标题相似度为主;作者名(artist_hints+各探针)命中该件作者 → +0.1(封顶 1.0)。
    ⚠️ artist_hints 只参与加分、绝不当标题探针——否则"以画家为题"的肖像画
    (如巴齐耶《奥古斯特·雷诺阿像》)会被候选作者名精确劫持(staging 真实误配)。
    label_lines_inv_only=True:墙签行只用来抽馆藏号,不做模糊/反向子串(墙签模式已摘出标题时;
    几十行 × 26 万标题名逐个模糊 prod 要十几分钟,且作者行会劫持同名肖像——模糊打 1.0、
    反向子串打 0.7,2026-10-06《Henri Edmond Cross》像与《晚风》并列)。"""
    raw_probes = [q for q in (list(queries) + list(label_lines)) if q]
    fuzzy_src = [q for q in queries if q] if label_lines_inv_only else raw_probes
    probes = [p for p in (normalize(q) for q in fuzzy_src) if p]
    hint_probes = probes + [
        normalize(a) for a in (artist_hints or []) if a and normalize(a)
    ]
    # 馆藏号精确匹配探针(候选名+墙签行,不含 artist_hints;归一化后长度≥3 才算)
    inv_probes = {
        i for i in (normalize_inv(q) for q in raw_probes) if len(i) >= _INV_MIN
    }
    # 脏 OCR 补抽:整行归一化抠不出号时,从全文正则抽馆藏号 token(先剥尺寸防污染)
    joined = " ".join(raw_probes)
    for tok in _INV_TOKEN.findall(_DIM.sub(" ", joined)):
        t = normalize_inv(tok)
        if len(t) >= _INV_MIN:
            inv_probes.add(t)
    # 反向子串:目录标题是否"出现在"整段 OCR 里
    ocr_norm = normalize(" ".join(fuzzy_src))
    if not probes:
        return []
    best: dict[str, float] = {}
    top: list[float] = []  # 目前最高的 limit 个分(小顶堆);进不了前 limit 的不必精确算
    for entry in index:
        title_score = 0.0
        if entry.get("inv") and entry["inv"] in inv_probes:
            title_score = 1.0  # 编号精确命中:满分,盖过模糊(下方再与加分取 min 封顶)
        # 反向子串:整行模糊被长墙签稀释时,目录标题(足够长)作为子串出现在 OCR 里即命中
        elif any(
            nm and len(nm) >= _REVSUB_MIN and nm in ocr_norm for nm in entry["names"]
        ):
            title_score = _REVSUB_SCORE
        # 剪枝门槛:加满作者分也 <LOW,或够不着第 limit 名(同分后来者排不进,stable sort)
        kth = top[0] - _ARTIST_BONUS if len(top) == limit else 0.0
        for p in probes:
            for name in entry["names"]:
                title_score = max(
                    title_score,
                    _sim_above(p, name, max(title_score, _FLOOR, kth)),
                )
        if title_score <= 0:
            continue
        artist_bonus = 0.0
        for p in hint_probes:
            for an in entry["artists"]:
                if an and (_sim(p, an) >= 0.8 or an in p or p in an):
                    artist_bonus = _ARTIST_BONUS
                    break
            if artist_bonus:
                break
        score = min(title_score + artist_bonus, 1.0)
        if score > best.get(entry["qid"], 0.0):
            best[entry["qid"]] = score
            if len(top) < limit:
                heapq.heappush(top, score)
            elif score > top[0]:
                heapq.heapreplace(top, score)
    return sorted(best.items(), key=lambda kv: -kv[1])[:limit]
