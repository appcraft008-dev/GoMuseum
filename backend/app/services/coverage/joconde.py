"""Joconde 区域适配器样板:按 Joconde 编号(external_ids["P347"])查 data.culture.gouv.fr
的 base-joconde-extrait 开放数据,取 localisation(展陈地)写成展陈证据。覆盖全法博物馆
——同一适配器喂任意法国馆,故为"区域适配器"样板。

调研实测(2026-07):
- 平台 opendatasoft,数据集 `base-joconde-extrait`(721629 条)。
- records 端点按 `reference` 过滤命中 1 条:reference == P347 值。
- 位置字段 `localisation`(如 "Valence ; musée des beaux-arts");`exposition` 为临展信息。
消费 Task 4 的 display_state.add_evidence(source="joconde", type="location_claim")。"""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.coverage.display_state import add_evidence

_UA = "GoMuseumEnrichment/1.0 (appcraft008@gmail.com)"
_RECORDS_URL = (
    "https://data.culture.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "base-joconde-extrait/records"
)
# 摘录进 detail 的原始字段(接地,可溯源)
_DETAIL_FIELDS = ("localisation", "exposition", "nom_officiel_musee")


def _default_http_get(url, params=None, headers=None, timeout=None):
    import requests

    time.sleep(0.2)  # 礼貌限速:公共开放数据,>=0.2s/请求
    return requests.get(url, params=params, headers=headers, timeout=timeout)


def fetch_joconde_evidence(joconde_ref: str, *, http_get=None) -> dict | None:
    """按 Joconde reference 查一条记录 → {"location": localisation|None, "detail": 字段摘录}。
    未命中/HTTP 错/异常 → None(容错,不崩上游批处理)。"""
    http_get = http_get or _default_http_get
    try:
        resp = http_get(
            _RECORDS_URL,
            params={
                "where": f'reference="{joconde_ref}"',
                "select": ",".join(("reference",) + _DETAIL_FIELDS),
                "limit": 1,
            },
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=30,
        )
        if getattr(resp, "status_code", 200) != 200:
            return None
        results = (resp.json() or {}).get("results") or []
    except Exception:
        return None
    if not results:
        return None
    rec = results[0]
    detail = " | ".join(f"{k}={rec[k]}" for k in _DETAIL_FIELDS if rec.get(k))
    return {"location": rec.get("localisation"), "detail": detail or None}


def enrich_museum_display(
    db: Session, museum_slug: str, *, fetch=None, limit=None
) -> dict:
    """遍历该馆有 P347 编号的对象 → Joconde 抓展陈地 → add_evidence。每 20 件提交一次。
    返回 {"checked": 有 P347 且已抓的件数, "evidenced": 写入证据的件数}。"""
    fetch = fetch or fetch_joconde_evidence
    museum = db.query(Museum).filter_by(slug=museum_slug).one_or_none()
    if museum is None:
        return {"checked": 0, "evidenced": 0}

    checked = evidenced = 0
    for obj in db.query(MuseumObject).filter_by(museum_id=museum.id).all():
        ref = ((obj.attributes or {}).get("external_ids") or {}).get("P347")
        if not ref:
            continue
        if limit is not None and checked >= limit:
            break
        checked += 1
        result = fetch(ref)
        if not result:
            continue
        add_evidence(
            obj,
            source="joconde",
            type="location_claim",
            location=result.get("location"),
            detail=result.get("detail"),
        )
        db.add(obj)
        evidenced += 1
        if evidenced % 20 == 0:
            db.commit()  # 逐批落盘:中途崩溃不丢已完成件

    db.commit()
    return {"checked": checked, "evidenced": evidenced}
