"""等价验证(spec 2026-10-10 §5):同一批作品,旧 SPARQL(行)与新 wbgetentities(转换成行)
喂同一套解析函数,逐字段比对。只读,不写库。

用法:python scripts/verify_wikidata_api_parity.py qids.txt out.jsonl
qids.txt 每行一个作品 qid(可附 "\t说明")。
"""

import json
import sys
import time

import requests

from app.services.enrichment import material as m
from app.services.enrichment import evidence as ev
from app.services.enrichment.sources import wikidata as _wd

LANGS = ["en", "zh", "zh-hant", "fr", "de", "es", "it", "ja", "ko", "pt"]

# ---- 旧 SPARQL 参照(从生产模块原样移来)----
_CREATOR_QUERY = """
SELECT ?artist ?rank ?cert (COUNT(?ref) AS ?refs) WHERE {{
  wd:{qid} p:P170 ?st .
  ?st ps:P170 ?artist ; wikibase:rank ?rank .
  OPTIONAL {{ ?st pq:P1480 ?cert . }}
  OPTIONAL {{ ?st prov:wasDerivedFrom ?ref . }}
}} GROUP BY ?artist ?rank ?cert
"""
_ARTIST_TITLES_QUERY = """
SELECT ?al_en ?al_cl WHERE {{
  OPTIONAL {{ ?a_en schema:about wd:{aqid} ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?al_en . }}
  OPTIONAL {{ ?a_cl schema:about wd:{aqid} ; schema:isPartOf <https://{cl}.wikipedia.org/> ; schema:name ?al_cl . }}
}} LIMIT 1
"""
_ARTIST_FACTS_BY_ARTIST_QUERY = """
SELECT ?birth ?death ?natLabel ?workLabel WHERE {{
  OPTIONAL {{ wd:{aqid} wdt:P569 ?birth. }}
  OPTIONAL {{ wd:{aqid} wdt:P570 ?death. }}
  OPTIONAL {{ wd:{aqid} wdt:P27 ?nat. }}
  OPTIONAL {{ wd:{aqid} wdt:P800 ?work. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""
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
_LABELS_QUERY = """
SELECT ?l WHERE {{ wd:{qid} rdfs:label ?l . FILTER(lang(?l) IN ({langs})) }}
"""
_ARTIST_I18N_FACTS_QUERY = """
SELECT ?natLabel ?work ?workLabel WHERE {{
  OPTIONAL {{ wd:{qid} wdt:P27 ?nat . ?nat rdfs:label ?natLabel .
             FILTER(lang(?natLabel) IN ({langs})) }}
  OPTIONAL {{ wd:{qid} wdt:P800 ?work . ?work rdfs:label ?workLabel .
             FILTER(lang(?workLabel) IN ({langs})) }}
}}
"""
_RICH_QUERY = """
SELECT ?pid ?vLabel WHERE {{
  VALUES ?prop {{ wdt:P88 wdt:P180 wdt:P186 wdt:P135 wdt:P136 wdt:P1343
                  wdt:P4969 wdt:P144 wdt:P941 wdt:P361 }}
  wd:{qid} ?prop ?v .
  ?p wikibase:directClaim ?prop . BIND(STRAFTER(STR(?p), "entity/") AS ?pid)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def sparql(q):
    for attempt in range(3):
        try:
            r = requests.get(
                _wd.SPARQL_ENDPOINT,
                params={"query": q, "format": "json"},
                headers={
                    "User-Agent": _wd.USER_AGENT,
                    "Accept": "application/sparql-results+json",
                },
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)


def old(qid):
    """旧实现语义:SPARQL 行 → 同一套解析函数;旧 P170 遍历与 rsplit 截断照旧复现。"""
    o = {}
    o["labels"] = m._labels_from_rows(
        sparql(
            _LABELS_QUERY.format(
                qid=qid, langs=", ".join('"%s"' % x for x in m._query_langs(LANGS))
            )
        ),
        LANGS,
    )
    aq = m._creator_from_rows(sparql(_CREATOR_QUERY.format(qid=qid)))
    o["creator"] = aq
    if aq:
        rows = sparql(_ARTIST_TITLES_QUERY.format(aqid=aq, cl="fr"))
        r0 = rows[0] if rows else {}
        o["artist_titles"] = {
            k: (r0.get(c) or {}).get("value", "").rsplit("/", 1)[-1]
            for k, c in (("en", "al_en"), ("fr", "al_cl"))
            if (r0.get(c) or {}).get("value")
        }
        frows = sparql(_ARTIST_FACTS_BY_ARTIST_QUERY.format(aqid=aq))
        o["artist_facts"] = m._artist_facts_from_rows(frows, aq)
        o["_works_full"] = _full(frows, "workLabel")
        wanted = m._i18n_wanted(LANGS)
        o["artist_i18n"] = m._artist_i18n_from_rows(
            sparql(
                _ARTIST_I18N_FACTS_QUERY.format(
                    qid=aq, langs=", ".join('"%s"' % x for x in wanted)
                )
            ),
            LANGS,
        )
    else:
        # 旧流水线:aqid 为空仍走 P170 遍历 —— 这里只记它会不会产出作者 qid(§4.1 假作者卡)
        rows = sparql(_ARTIST_FACTS_QUERY.format(qid=qid))
        au = next(
            ((r.get("artist") or {}).get("value", "") for r in rows if r.get("artist")),
            "",
        )
        o["traversal_artist_qid"] = au.rsplit("/", 1)[-1] if au else None
    rrows = sparql(_RICH_QUERY.format(qid=qid))
    o["rich"] = ev._rich_from_rows(rrows)
    o["_rich_full"] = _rich_full(rrows)
    return o


def _full(rows, col):
    """截断前的完整值集合(去掉原始 QID 占位)—— 用来区分「截取前 5 个选得不同」与真实不等价。"""
    return sorted(
        {
            (r.get(col) or {}).get("value")
            for r in rows
            if (r.get(col) or {}).get("value")
            and not m._is_raw_qid((r.get(col) or {}).get("value"))
        }
    )


def _rich_full(rows):
    return sorted(
        {
            ((r.get("pid") or {}).get("value"), (r.get("vLabel") or {}).get("value"))
            for r in rows
            if (r.get("vLabel") or {}).get("value")
            and not m._is_raw_qid((r.get("vLabel") or {}).get("value"))
        }
    )


def new(qid):
    o = {
        "labels": m.fetch_wikidata_labels(qid, LANGS),
        "creator": m.resolve_creator_qid(qid),
    }
    aq = o["creator"]
    if aq:
        ent = m._wa.get_entities([aq], props="sitelinks").get(aq) or {}
        sl = ent.get("sitelinks") or {}
        o["artist_titles"] = {
            k: sl[w]["title"]
            for k, w in (("en", "enwiki"), ("fr", "frwiki"))
            if sl.get(w)
        }
        o["artist_facts"] = m.fetch_artist_facts(qid, artist_qid=aq)
        ent = m._wa.get_entities([aq], props="claims").get(aq) or {}
        o["_works_full"] = _full(
            m._artist_fact_rows(ent, m._wa.get_entities), "workLabel"
        )
        o["artist_i18n"] = m.fetch_artist_i18n_facts(aq, LANGS)
    else:
        o["traversal_artist_qid"] = m.fetch_artist_facts(qid).get("artist_qid")
    o["rich"] = ev.fetch_rich_facts(qid)
    went = (
        m._wa.get_entities([qid], props="claims").get(qid) or {}
        if qid.startswith("Q")
        else {}
    )
    o["_rich_full"] = _rich_full(ev._rich_rows(went, m._wa.get_entities))
    return o


def _norm(v):
    """顺序无关的规范形:列表排序、字典递归。"""
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in sorted(v.items())}
    if isinstance(v, list):
        return sorted(
            (_norm(x) for x in v),
            key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True),
        )
    return v


def classify(a, b):
    if a == b:
        return "identical"
    if _norm(a) == _norm(b):
        return "order_only"
    return "DIFF"


def _cap_check(k, c, a, b):
    """多值字段每项只取前 5:旧 SPARQL 行序不保证,新按 Wikidata 语句顺序。完整集合相同、
    其余字段一致、两边所选都出自该集合 → 「截断选集不同」,不算不等价。"""
    if c != "DIFF" or k not in ("artist_facts", "rich"):
        return c
    full = "_works_full" if k == "artist_facts" else "_rich_full"
    if a.get(full) != b.get(full):
        return "DIFF"
    if k == "artist_facts":
        strip = lambda d: {
            x: y for x, y in (d or {}).items() if x != "artist_notable_works"
        }  # noqa: E731
        if strip(a[k]) != strip(b[k]):
            return "DIFF"
        pool = set(a[full])
        ok = all(
            w in pool
            for d in (a[k], b[k])
            for w in (d or {}).get("artist_notable_works", [])
        )
    else:
        pool = set(map(tuple, a[full]))
        ok = all(
            (f["source"].split(":")[1], f["value"]) in pool
            for d in (a[k], b[k])
            for f in d
        )
    return "cap_selection" if ok else "DIFF"


def main(qfile, out):
    qids = [line.split("\t")[0].strip() for line in open(qfile) if line.strip()]
    summary = {}
    with open(out, "w") as f:
        for qid in qids:
            rec = {"qid": qid}
            try:
                a, b = old(qid), new(qid)
            except Exception as e:  # 记录并继续;报告里单列
                rec["error"] = repr(e)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                summary["error"] = summary.get("error", 0) + 1
                continue
            for k in sorted(k for k in set(a) | set(b) if not k.startswith("_")):
                c = classify(a.get(k), b.get(k))
                c = _cap_check(k, c, a, b)
                rec[k] = c
                summary[(k, c)] = summary.get((k, c), 0) + 1
                if c == "DIFF":
                    rec[k + "_old"], rec[k + "_new"] = a.get(k), b.get(k)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    for k, v in sorted(summary.items(), key=str):
        print(k, v)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
