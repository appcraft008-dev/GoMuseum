"""逐件材料富化：给一件（qid + 外部ID + wiki 标题）按需路由富化源、抓材料、merge。

= 把 Fetcher 一锅式抓取的「逐件富化」半边抽出，供生成时按需调用（spec §6 列目录/抓材料解耦）。
"""

from __future__ import annotations

from app.services.enrichment.fetcher import _CORE
from app.services.enrichment.merge import merge_contributions
from app.services.enrichment.sources import wikidata as _wd


def fetch_object_material(
    qid: str, external_ids: dict, wiki_titles: dict, registry
) -> dict:
    """路由富化源→enrich→merge，返回材料 attributes（剥身份/留痕键）。无贡献→{}。"""
    context = {"wiki_titles": wiki_titles or {}}
    contribs = []
    for src in registry.route(external_ids or {}):
        c = src.enrich(qid, external_ids or {}, context)
        if c is not None:
            contribs.append(c)
    if not contribs:
        return {}
    merged = merge_contributions(contribs)
    merged.pop("image_url", None)
    return {k: v for k, v in merged.items() if k not in _CORE}


_ARTIST_QUERY = """
SELECT ?al_en ?al_cl WHERE {{
  wd:{qid} wdt:P170 ?artist .
  OPTIONAL {{ ?a_en schema:about ?artist ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?al_en . }}
  OPTIONAL {{ ?a_cl schema:about ?artist ; schema:isPartOf <https://{cl}.wikipedia.org/> ; schema:name ?al_cl . }}
}} LIMIT 1
"""


def _default_artist_query(sparql):
    import requests

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


def fetch_artist_material(qid, registry, *, run_query=None, country_lang="fr") -> dict:
    """抓作者实体 Wikipedia(作品→P170→作者维基标题→extract)。无作者/无维基→{}。"""
    run_query = run_query or _default_artist_query
    rows = run_query(_ARTIST_QUERY.format(qid=qid, cl=country_lang or "fr"))
    if not rows:
        return {}
    row = rows[0]
    titles = {}
    se = (row.get("al_en") or {}).get("value")
    if se:
        titles["en"] = se.rsplit("/", 1)[-1]
    scl = (row.get("al_cl") or {}).get("value")
    if scl:
        titles[country_lang or "fr"] = scl.rsplit("/", 1)[-1]
    if not titles:
        return {}
    wiki = registry.get("wikipedia")
    if wiki is None:
        return {}
    contrib = wiki.enrich(qid, {}, {"wiki_titles": titles})
    if contrib is None:
        return {}
    return {
        f"artist_{k}": v
        for k, v in contrib.fields.items()
        if k.startswith("extract_") and v
    }
