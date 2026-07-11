"""雕塑多视角补图:Wikidata→Commons 分类→他人照片规范 URL 注入既有图管线。

基准显示雕塑在真实照片上 Top-1 仅 ~33%(索引每件≈1 图)。这里给 sculpture 件补
多视角 Commons 照片行(role="view"),由 materializer 物化时自动嵌入(Task 3 钩子)。
逻辑参照 bench `commons_alt_photos`,但独立实现于管线、带 http_get 注入可测,
不 import bench 代码。license/credit 留空——物化时经 materializer 的 fetch_meta 补。"""

from __future__ import annotations

import time
from urllib.parse import quote

from app.models.museum_object import ObjectImage

_UA = "GoMuseumEnrichment/1.0 (appcraft008@gmail.com)"
_WD_API = "https://www.wikidata.org/w/api.php"
_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_IMG_EXT = (".jpg", ".jpeg", ".png")


def _default_http_get(url: str, params: dict) -> dict:
    import requests

    time.sleep(0.2)  # 礼貌限速
    r = requests.get(url, params=params, headers={"User-Agent": _UA}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_view_urls(qid: str, *, max_n: int = 4, http_get=None) -> list[str]:
    """qid → P373/commonswiki 分类 → 分类内他人照片(排除 P18 本尊)的 Special:FilePath 规范 URL。"""
    http_get = http_get or _default_http_get
    ent = http_get(
        _WD_API,
        {
            "action": "wbgetentities",
            "ids": qid,
            "props": "claims|sitelinks",
            "format": "json",
        },
    )["entities"][qid]
    claims = ent.get("claims", {})

    def _claim_str(pid):
        c = claims.get(pid)
        if not c:
            return None
        # novalue/somevalue snak 无 datavalue
        return (c[0]["mainsnak"].get("datavalue") or {}).get("value")

    p18 = _claim_str("P18")
    cat = _claim_str("P373")
    if not cat:
        link = (ent.get("sitelinks") or {}).get("commonswiki", {}).get("title", "")
        cat = link.removeprefix("Category:") if link.startswith("Category:") else None
    if not cat:
        return []

    members = http_get(
        _COMMONS_API,
        {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{cat}",
            "cmtype": "file",
            "cmlimit": 50,
            "format": "json",
        },
    )["query"]["categorymembers"]

    urls: list[str] = []
    for member in members:
        fname = member["title"].removeprefix("File:")
        if p18 and fname.replace(" ", "_") == p18.replace(" ", "_"):
            continue  # 排除官方图本尊
        if not fname.lower().endswith(_IMG_EXT):
            continue
        # Special:FilePath 规范 URL(与 P18 管线图同格式):materializer 下载时自动加
        # ?width=1600 服务端缩放,fetch_meta 可由 basename 反查署名——免 imageinfo 调用
        urls.append(
            f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(fname)}"
        )
        if len(urls) >= max_n:
            break
    return urls


def add_view_images(db, obj, *, max_total: int = 5, fetch=None) -> int:
    """sculpture 且现有图 <3 时,补 role="view" 参考图至总数 ≤ max_total。
    已有同 source_url 跳过(幂等);不 commit(调用方管事务);返回新插行数。"""
    if obj.category != "sculpture":
        return 0
    existing = (
        db.query(ObjectImage)
        .filter_by(object_id=obj.id)
        .order_by(ObjectImage.sort)
        .all()
    )
    if len(existing) >= 3:
        return 0

    fetch = fetch or (lambda qid, max_n: fetch_view_urls(qid, max_n=max_n))
    have = {img.source_url for img in existing}
    next_sort = max((img.sort or 0 for img in existing), default=-1) + 1
    room = max_total - len(existing)

    inserted = 0
    for url in fetch(obj.qid, room):
        if inserted >= room:
            break
        if url in have:
            continue
        db.add(
            ObjectImage(object_id=obj.id, role="view", source_url=url, sort=next_sort)
        )
        have.add(url)
        next_sort += 1
        inserted += 1
    db.flush()
    return inserted
