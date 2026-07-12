"""WikidataCatalog：用现有 Wikidata SPARQL 主干列对象、产 StubRecord。
复用 wikidata.QUERY/_v/_PAGE；run_query 注入式（默认真实 SPARQL）。spec §4。
注：现有 WikidataSource.fetch 保留不动；Phase B 才让 Fetcher 改用本类。"""

from __future__ import annotations

import time
from typing import Iterable

import requests

from app.services.enrichment.catalog_source import CatalogSource, StubRecord
from app.services.enrichment.category_config import category_for
from app.services.enrichment.sources import wikidata as _wd


def _default_run_query(sparql: str) -> list[dict]:
    r = requests.get(
        _wd.SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={
            "User-Agent": _wd.USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


_CATALOG_PAGE = 2000  # 目录翻页页宽(与 _wd._PAGE=200 解耦;大页少翻避开深OFFSET超时)


class WikidataCatalog(CatalogSource):
    name = "wikidata"

    def __init__(self, run_query=None):
        self._run_query = run_query or _default_run_query

    def list(self, cfg) -> Iterable[StubRecord]:
        cats = cfg.categories or [cfg.category_filter]
        cat_values = " ".join(f"wd:{q}" for q in cats)
        # 多 P31 作品每个类型一行:缓冲按 qid 归并,已知类目优先于 unknown(行序无关)
        records: dict[str, StubRecord] = {}
        fetched = 0
        offset = 0
        empty_retries = 0
        while fetched < cfg.fetch_limit:
            # 大页少翻:每页都要全集 ORDER BY,深 OFFSET×小页(200)在 WDQS 反复超时
            # (实证 2026-07-11:两次静默截断 1537/1517,漏收长尾件)
            page = min(_CATALOG_PAGE, cfg.fetch_limit - fetched)
            rows = self._run_query(
                _wd.QUERY.format(
                    museum=cfg.wikidata_qid,
                    cat_values=cat_values,
                    country_lang=(cfg.country_lang or "fr"),
                    limit=page,
                    offset=offset,
                )
            )
            if not rows:
                # 空页≠到底:WDQS 超时也返回空——重试再判(批处理纪律:外部查询重试)
                if empty_retries < 2:
                    empty_retries += 1
                    if self._run_query is _default_run_query:
                        time.sleep(5)
                    continue
                break
            empty_retries = 0
            for row in rows:
                qid = row["item"]["value"].rsplit("/", 1)[-1]
                p31 = (row.get("p31", {}) or {}).get("value", "").rsplit("/", 1)[-1]
                if qid in records:
                    prev = records[qid]
                    if prev.category == category_for(None):  # unknown → 可升级
                        cat = category_for(p31)
                        if cat != category_for(None):
                            prev.category = cat
                    img = _wd._v(row, "image")
                    if img and img not in prev.image_urls:  # P18 多值:累积多角度图
                        prev.image_urls.append(img)
                    continue
                ext = {}
                jo = _wd._v(row, "joconde")
                if jo:
                    ext["P347"] = jo
                titles = {}
                se = _wd._v(row, "sitelink_en")
                if se:
                    titles["en"] = se.rsplit("/", 1)[-1]
                scl = _wd._v(row, "sitelink_cl")
                if scl:
                    titles[cfg.country_lang or "fr"] = scl.rsplit("/", 1)[-1]
                first_img = _wd._v(row, "image")
                p276 = (_wd._v(row, "p276") or "").rsplit("/", 1)[-1] or None
                row["p276_qid"] = p276
                records[qid] = StubRecord(
                    inventory_number=_wd._v(row, "inventory"),
                    qid=qid,
                    title=_wd._v(row, "label_en"),
                    artist=_wd._v(row, "creator_en"),
                    year=_wd._v(row, "year"),
                    category=category_for(p31),
                    image_url=_wd._v(row, "image"),
                    popularity=int(_wd._v(row, "links") or 0),
                    owning_museum=cfg.slug,
                    source="wikidata",
                    raw=row,
                    external_ids=ext,
                    wiki_titles=titles,
                    image_urls=[first_img] if first_img else [],
                )
            fetched += len(rows)
            offset += len(rows)
            if self._run_query is _default_run_query:
                time.sleep(1)
        yield from records.values()  # dict 保插入序(热度降序)
