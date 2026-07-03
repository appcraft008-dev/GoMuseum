"""匹配层(识别的不变核心;P2 换 CLIP 引擎也不动它):
候选名/墙签行 → 该馆目录多语模糊匹配 → [(qid, score)] 降序。
R1 接地:身份只可能来自这里匹配到的真实目录记录。
stdlib difflib(~2000 件毫秒级,零新依赖);索引进程内缓存 TTL 600s。"""

from __future__ import annotations

import re
import time
import unicodedata
from difflib import SequenceMatcher

from app.models.artist import Artist
from app.models.museum_object import MuseumObject

HIGH = 0.85  # ≥ 直开讲解页;真实数据校准前的初值
LOW = 0.5  # < 未收录;[LOW, HIGH) 出确认卡

_INDEX_TTL = 600  # 秒
_index_cache: dict = {}  # museum_id -> (ts, index)

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"[\s_]+")


def normalize(s: str) -> str:
    """小写/NFD 去音符/去标点/压空白(Théodore≈Theodore)。"""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = _PUNCT.sub(" ", s.lower())
    return _WS.sub(" ", s).strip()


def build_index(db, museum_id) -> list[dict]:
    """馆目录 → [{"qid", "names": set, "artists": set}](归一化;进程内缓存)。"""
    hit = _index_cache.get(museum_id)
    if hit and time.time() - hit[0] < _INDEX_TTL:
        return hit[1]
    artists_by_qid = {}
    for a in db.query(Artist).all():
        names = {normalize(v) for v in (a.name_i18n or {}).values() if v}
        if a.name_en:
            names.add(normalize(a.name_en))
        artists_by_qid[a.qid] = names
    index = []
    for o in db.query(MuseumObject).filter_by(museum_id=museum_id).all():
        attrs = o.attributes or {}
        names = {normalize(v) for v in (attrs.get("title_i18n") or {}).values() if v}
        for col in (o.title_en, o.title_zh):
            if col:
                names.add(normalize(col))
        artist_names = set(artists_by_qid.get(attrs.get("artist_qid"), set()))
        for col in (o.artist_en, o.artist_zh):
            if col:
                artist_names.add(normalize(col))
        index.append(
            {"qid": o.qid, "names": names - {""}, "artists": artist_names - {""}}
        )
    _index_cache[museum_id] = (time.time(), index)
    return index


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def match(index: list[dict], queries: list[str], label_lines: list[str]) -> list:
    """查询串(候选名)+墙签行 → [(qid, score)] 降序去重。
    标题相似度为主;查询/墙签行中出现该件作者名 → +0.1(封顶 1.0)。"""
    probes = [normalize(q) for q in (list(queries) + list(label_lines)) if q]
    probes = [p for p in probes if p]
    if not probes:
        return []
    best: dict[str, float] = {}
    for entry in index:
        title_score = max(
            (_sim(p, name) for p in probes for name in entry["names"]), default=0.0
        )
        if title_score <= 0:
            continue
        artist_bonus = 0.0
        for p in probes:
            for an in entry["artists"]:
                if an and (_sim(p, an) >= 0.8 or an in p or p in an):
                    artist_bonus = 0.1
                    break
            if artist_bonus:
                break
        score = min(title_score + artist_bonus, 1.0)
        if score > best.get(entry["qid"], 0.0):
            best[entry["qid"]] = score
    return sorted(best.items(), key=lambda kv: -kv[1])
