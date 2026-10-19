"""身份去重：多源 StubRecord 按强键归并成一对象。
Phase A 只做强键去重+首条胜（单源 pass-through）；字段级合并(§5b)+模糊匹配 Phase B。
spec §5。"""

from __future__ import annotations

import re

from app.services.enrichment.catalog_source import StubRecord

_WIKIDATA_QID = re.compile(r"^Q\d+$")


def is_wikidata_qid(qid: str | None) -> bool:
    """真 Wikidata QID(Q+数字)?非 Wikidata 源合成的对外把手(如 joconde-<ref>)返回 False。
    用于跳过只对真 QID 有意义的 Wikidata SPARQL(既省成本又避免 wd:<合成号> 垃圾查询)。"""
    return bool(qid and _WIKIDATA_QID.match(qid))


def _norm_inv(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _key(r: StubRecord):
    if r.owning_museum and r.inventory_number:
        return ("inv", r.owning_museum, _norm_inv(r.inventory_number))
    if r.qid:
        return ("qid", r.qid)
    return ("uid", id(r))


def _creators(r: StubRecord) -> set:
    return set((r.raw or {}).get("creator_qids") or ())


def _distinct_work(a: StubRecord, b: StubRecord) -> bool:
    """同馆同号的两条是不是两件作品:都是 Wikidata 条目、qid 不同、作者都已知且毫无交集。
    奥赛油画/雕塑两套 RF 编号撞号(RF 166 = Regnault 油画 = Chapu 雕塑)走这条;
    作者有交集的多是 Wikidata 重复条目或同一画布正反面,仍当一件。"""
    ca, cb = _creators(a), _creators(b)
    return bool(
        is_wikidata_qid(a.qid)
        and is_wikidata_qid(b.qid)
        and a.qid != b.qid
        and ca
        and cb
        and not ca & cb
    )


def merge_stubs(records: list[StubRecord]) -> list[StubRecord]:
    """强键去重（(馆,馆藏号)>qid），首条胜;同号但确属另一件作品的不并(见 _distinct_work)。"""
    seen: dict = {}
    out: list[StubRecord] = []
    for r in records:
        k = _key(r)
        if any(not _distinct_work(p, r) for p in seen.get(k, ())):
            continue
        seen.setdefault(k, []).append(r)
        out.append(r)
    return out
