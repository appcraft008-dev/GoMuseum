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


# zh 标签变体优先级:简体权威 > 大陆简体 > 笼统 zh(可能繁体;比没有强)
_ZH_VARIANTS = ("zh-hans", "zh-cn", "zh")

_t2s = None


def to_simplified(s: str) -> str:
    """繁→简(OpenCC 确定性字符转换;马奈/高更等 Wikidata 只有繁体 zh 标签)。
    不用 LLM——人名转换必须精确对应,不能自由发挥。"""
    global _t2s
    if _t2s is None:
        from opencc import OpenCC

        _t2s = OpenCC("t2s")
    return _t2s.convert(s or "")


def fetch_wikidata_labels(qid: str, langs: list, *, run_query=None) -> dict:
    """Wikidata 实体在 langs 的官方标签 → {lang: label}(只含有的)。
    zh 按 zh-hans > zh-cn > zh 取(修繁简混杂:愛德華·馬奈类)。"""
    run_query = (
        run_query or _default_artist_query
    )  # ponytail: same generic SPARQL caller
    query_langs = list(langs)
    if "zh" in langs:
        query_langs += [v for v in _ZH_VARIANTS if v not in query_langs]
    langlist = ", ".join('"%s"' % x for x in query_langs)
    rows = run_query(_LABELS_QUERY.format(qid=qid, langs=langlist))
    raw: dict = {}
    for row in rows:
        lv = row.get("l") or {}
        lang = lv.get("xml:lang") or lv.get("lang")
        val = lv.get("value")
        if lang and val and lang not in raw:
            raw[lang] = val
    out = {}
    for lang in langs:
        if lang == "zh":
            for v in _ZH_VARIANTS:
                if raw.get(v):
                    # 取自笼统 zh 变体的可能是繁体 → t2s;hans/cn 转换是无害幂等
                    out["zh"] = to_simplified(raw[v])
                    break
        elif raw.get(lang):
            out[lang] = raw[lang]
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


_ARTIST_I18N_FACTS_QUERY = """
SELECT ?natLabel ?workLabel WHERE {{
  OPTIONAL {{ wd:{qid} wdt:P27 ?nat . ?nat rdfs:label ?natLabel .
             FILTER(lang(?natLabel) IN ({langs})) }}
  OPTIONAL {{ wd:{qid} wdt:P800 ?work . ?work rdfs:label ?workLabel .
             FILTER(lang(?workLabel) IN ({langs})) }}
}}
"""


def fetch_artist_i18n_facts(artist_qid, langs, *, run_query=None) -> dict:
    """作者国籍(P27)/代表作(P800)的多语权威标签(交接③:作者卡本地化)。
    单查询 rdfs:label 语言过滤(同 _LABELS_QUERY 款,一作者一查)。
    返回 {"nationality_i18n": {lang: label}, "notable_works_i18n": {lang: [labels]}};
    无标签的语言缺席(由调用方翻译兜底)。"""
    run_query = run_query or _default_artist_query
    langlist = ", ".join('"%s"' % x for x in langs)
    rows = run_query(_ARTIST_I18N_FACTS_QUERY.format(qid=artist_qid, langs=langlist))
    nat_i18n: dict = {}
    works_i18n: dict = {}
    for row in rows:
        nl = row.get("natLabel") or {}
        wl = row.get("workLabel") or {}
        nlang, nv = nl.get("xml:lang") or nl.get("lang"), nl.get("value")
        wlang, wv = wl.get("xml:lang") or wl.get("lang"), wl.get("value")
        if nv and nlang in langs and not _is_raw_qid(nv) and nlang not in nat_i18n:
            nat_i18n[nlang] = to_simplified(nv) if nlang == "zh" else nv
        if wv and wlang in langs and not _is_raw_qid(wv):
            if wlang == "zh":
                wv = to_simplified(wv)
            works_i18n.setdefault(wlang, [])
            if wv not in works_i18n[wlang]:
                works_i18n[wlang].append(wv)
    return {
        "nationality_i18n": nat_i18n,
        "notable_works_i18n": {k: v[:5] for k, v in works_i18n.items()},
    }
