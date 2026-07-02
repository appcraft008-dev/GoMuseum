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


def _is_raw_qid(v: str) -> bool:
    """wikibase:label 对无本地化标签的实体退回原始 QID/PID(如 'Q17490760')。"""
    return bool(v) and v[0] in "QP" and v[1:].isdigit()


_ARTIST_FACTS_QUERY = """
SELECT ?artist ?birth ?death ?natLabel ?workLabel WHERE {{
  wd:{qid} wdt:P170 ?artist .
  OPTIONAL {{ ?artist wdt:P569 ?birth. }}
  OPTIONAL {{ ?artist wdt:P570 ?death. }}
  OPTIONAL {{ ?artist wdt:P27 ?nat. }}
  OPTIONAL {{ ?artist wdt:P800 ?work. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def fetch_artist_facts(qid, *, run_query=None) -> dict:
    """作者 Wikidata 实体结构化属性 → {artist_birth/death/nationality/notable_works}。无→{}。"""
    run_query = run_query or _default_artist_query
    rows = run_query(_ARTIST_FACTS_QUERY.format(qid=qid))
    if not rows:
        return {}
    out = {}
    works = []
    for row in rows:
        b = (row.get("birth") or {}).get("value")
        d = (row.get("death") or {}).get("value")
        nat = (row.get("natLabel") or {}).get("value")
        w = (row.get("workLabel") or {}).get("value")
        # 标签服务对无本地化标签的实体退回原始 QID → 无意义,跳过
        if nat and _is_raw_qid(nat):
            nat = None
        if w and _is_raw_qid(w):
            w = None
        if "artist_qid" not in out:
            au = (row.get("artist") or {}).get("value", "")
            if au:
                out["artist_qid"] = au.rsplit("/", 1)[-1]
        if b and "artist_birth" not in out:
            out["artist_birth"] = b[:4]
        if d and "artist_death" not in out:
            out["artist_death"] = d[:4]
        if nat and "artist_nationality" not in out:
            out["artist_nationality"] = nat
        if w and w not in works:
            works.append(w)
    if works:
        out["artist_notable_works"] = works[:5]
    return out


_LABELS_QUERY = """
SELECT ?l WHERE {{ wd:{qid} rdfs:label ?l . FILTER(lang(?l) IN ({langs})) }}
"""


def fetch_wikidata_labels(qid: str, langs: list, *, run_query=None) -> dict:
    """Wikidata 实体在 langs 的官方标签 → {lang: label}(只含有的)。"""
    run_query = (
        run_query or _default_artist_query
    )  # ponytail: same generic SPARQL caller
    langlist = ", ".join('"%s"' % x for x in langs)
    rows = run_query(_LABELS_QUERY.format(qid=qid, langs=langlist))
    out = {}
    for row in rows:
        lv = row.get("l") or {}
        lang = lv.get("xml:lang") or lv.get("lang")
        val = lv.get("value")
        if lang in langs and val and lang not in out:
            out[lang] = val
    return out


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
