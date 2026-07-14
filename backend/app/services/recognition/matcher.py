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
_NONALNUM = re.compile(r"[^a-z0-9]+")
_INV_MIN = 3  # 归一化后长度 <3 不做编号匹配(防误伤)
# 从整段 OCR 抽馆藏号样式 token(≥2 字母前缀 + 至多 3 段数字)。脏 OCR 把标题/号/尺寸
# 挤一行时,整行 normalize_inv 抠不出号,靠此正则补(实测 0.55→1.0)。数字段有界,避免
# 贪婪吞掉紧随的尺寸位;抽号前先剥"74x94cm"类尺寸,防污染。
_DIM = re.compile(r"\d+\s*[x×]\s*\d+\s*(?:cm|mm|in)?", re.IGNORECASE)
_INV_TOKEN = re.compile(r"[A-Za-z]{2,4}\s?\d{1,5}(?:[\s\-]\d{1,4}){0,2}")
_REVSUB_MIN = 8  # 反向子串:目录名归一化 ≥8 字符才算"出现在 OCR 里"(防短标题误报)
_REVSUB_SCORE = 0.7  # 反向子串命中分(≥LOW 出候选卡,<HIGH 不直判)


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
    """馆目录 → [{"qid","names","artists","inv"}](归一化;进程内缓存)。
    museum_id=None → 全部馆(去 filter,None 为全局索引的缓存键)。"""
    hit = _index_cache.get(museum_id)
    if hit and time.time() - hit[0] < _INDEX_TTL:
        return hit[1]
    artists_by_qid = {}
    for a in db.query(Artist).all():
        names = {normalize(v) for v in (a.name_i18n or {}).values() if v}
        if a.name_en:
            names.add(normalize(a.name_en))
        artists_by_qid[a.qid] = names
    q = db.query(MuseumObject)
    if museum_id is not None:
        q = q.filter_by(museum_id=museum_id)
    index = []
    for o in q.all():
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
            {
                "qid": o.qid,
                "names": names - {""},
                "artists": artist_names - {""},
                "inv": normalize_inv(o.inventory_number) or None,
            }
        )
    _index_cache[museum_id] = (time.time(), index)
    return index


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def match(
    index: list[dict],
    queries: list[str],
    label_lines: list[str],
    artist_hints: list[str] | None = None,
) -> list:
    """查询串(候选题名)+墙签行 → [(qid, score)] 降序去重。
    标题相似度为主;作者名(artist_hints+各探针)命中该件作者 → +0.1(封顶 1.0)。
    ⚠️ artist_hints 只参与加分、绝不当标题探针——否则"以画家为题"的肖像画
    (如巴齐耶《奥古斯特·雷诺阿像》)会被候选作者名精确劫持(staging 真实误配)。"""
    raw_probes = [q for q in (list(queries) + list(label_lines)) if q]
    probes = [p for p in (normalize(q) for q in raw_probes) if p]
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
    ocr_norm = normalize(joined)  # 反向子串:目录标题是否"出现在"整段 OCR 里
    if not probes:
        return []
    best: dict[str, float] = {}
    for entry in index:
        title_score = max(
            (_sim(p, name) for p in probes for name in entry["names"]), default=0.0
        )
        # 反向子串:整行模糊被长墙签稀释时,目录标题(足够长)作为子串出现在 OCR 里即命中
        if title_score < _REVSUB_SCORE and any(
            nm and len(nm) >= _REVSUB_MIN and nm in ocr_norm for nm in entry["names"]
        ):
            title_score = _REVSUB_SCORE
        if entry.get("inv") and entry["inv"] in inv_probes:
            title_score = 1.0  # 编号精确命中:满分,盖过模糊(下方再与加分取 min 封顶)
        if title_score <= 0:
            continue
        artist_bonus = 0.0
        for p in hint_probes:
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
