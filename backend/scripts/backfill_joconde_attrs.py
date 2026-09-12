"""回填 Joconde 法语字段到 museum_objects.attributes(2026-07-22 断供期的存量补课)。

背景:文化部 2026-06-01 关停 Opendatasoft 门户,但老 API 实际活到 2026-07-22 才断;
断供被 material.py 的单源容错静默吞掉,此后生成的件都缺这一路材料。详见
app/services/enrichment/sources/joconde.py 模块头。

⚠️**本脚本只写 attributes,绝不碰 object_content_sections。**
展签面板(museum_repo 的 facts)是每次请求实时从 attributes 读的 ——
`dimensions` 直接读、`medium` 回退读 —— 所以补 attributes 就能让面板复活,
**不必重新生成正文**。而重生成正文会清空 audio_key 让已发布内容静默变哑
(受影响件上有 707 段已生成音频)。这是本脚本存在的全部理由:拿到面板收益,
不付音频重灌的代价。以后改这个脚本的人请守住这条线。

只补缺、不覆盖已有非空值:某些字段可能来自别的源(如 Wikidata P186 材质),
那是有意的优先级,不该被这次补课冲掉。

用法:
    python scripts/backfill_joconde_attrs.py                 # dry-run
    python scripts/backfill_joconde_attrs.py --apply
    python scripts/backfill_joconde_attrs.py --museum louvre --limit 50 --apply
幂等,可重跑(已补齐的自动跳过);中断后重跑即续。
"""

import argparse
import sys
import time

sys.path.insert(0, "/app")

import requests  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.museum import Museum  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.enrichment.sources.joconde import (  # noqa: E402
    _FIELD_MAP,
    TABULAR_URL,
    resolve_resource_id,
)

_UA = "GoMuseumEnrichment/1.0 (appcraft008@gmail.com)"
_BATCH = 100  # 实测 100 个 ref 一次请求 0.9s、URL 1.5KB;上游限流 100 req/s
_PAUSE = 0.3  # 礼貌限速(远低于上游限额)


def _get_json(url, params=None):
    r = requests.get(
        url,
        params=params,
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json() or {}


def fetch_batch(rid: str, refs: list[str]) -> dict[str, dict]:
    """一批 ref → {ref: 行}。未命中的 ref 不在返回里。"""
    data = _get_json(
        TABULAR_URL.format(rid=rid),
        {"Reference__in": ",".join(refs), "page_size": len(refs)},
    )
    return {r["Reference"]: r for r in (data.get("data") or []) if r.get("Reference")}


def plan(obj: MuseumObject, row: dict) -> dict:
    """这件要新增哪些键(只补缺:已有非空值一律保留)。"""
    attrs = obj.attributes or {}
    out = {}
    for key, col in _FIELD_MAP.items():
        val = row.get(col)
        if val not in (None, "") and attrs.get(key) in (None, ""):
            out[key] = val
    return out


def main(apply: bool, museum: str | None, limit: int | None) -> None:
    db = SessionLocal()
    q = db.query(MuseumObject).filter(
        MuseumObject.attributes["external_ids"].has_key("P347")  # noqa: W601
    )
    if museum:
        m = db.query(Museum).filter_by(slug=museum).one_or_none()
        if m is None:
            raise SystemExit(f"museum not found: {museum}")  # typo 别静默 0/0
        q = q.filter(MuseumObject.museum_id == m.id)

    todo = []
    for o in q.all():
        ref = ((o.attributes or {}).get("external_ids") or {}).get("P347")
        # domaine_fr 是 Joconde 独有键:有它就是这一路已经补过了
        if ref and not (o.attributes or {}).get("domaine_fr"):
            todo.append((o, ref))
    if limit:
        todo = todo[:limit]
    print(f"带 P347 待补 {len(todo)} 件", flush=True)
    if not todo:
        return

    rid = resolve_resource_id(_get_json)
    print(f"CSV 资源 id = {rid}", flush=True)

    filled = missed = 0
    fields_added = 0
    for i in range(0, len(todo), _BATCH):
        chunk = todo[i : i + _BATCH]
        rows = fetch_batch(rid, [ref for _, ref in chunk])
        for o, ref in chunk:
            row = rows.get(ref)
            if row is None:
                missed += 1
                continue
            add = plan(o, row)
            if not add:
                continue
            if apply:
                # JSONB 要整体重新赋值才会被 SQLAlchemy 标脏
                o.attributes = {**(o.attributes or {}), **add}
            filled += 1
            fields_added += len(add)
        if apply:
            db.commit()  # 逐批落盘:中途崩溃不丢已完成批
        print(
            f"  [{min(i + _BATCH, len(todo))}/{len(todo)}] "
            f"已补 {filled} 件 / 上游未命中 {missed}",
            flush=True,
        )
        time.sleep(_PAUSE)

    mode = "已回填" if apply else "dry-run(加 --apply 生效)"
    print(
        f"{mode}: 补齐 {filled} 件、新增字段 {fields_added} 个、"
        f"上游未命中 {missed} 件。未改动任何 object_content_sections。"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--museum", help="只补某馆(slug)")
    p.add_argument("--limit", type=int, help="只处理前 N 件(试跑)")
    a = p.parse_args()
    main(a.apply, a.museum, a.limit)
