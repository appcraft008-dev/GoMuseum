"""证据包组装:结构原子事实 + 标源叙事块 + LLM 抽争议。spec 2026-06-29-evidence-pack。"""

from __future__ import annotations

from app.services.enrichment.sources import wikidata as _wd

# 富属性 → (claim 中文名, lane topic)。结构化 → type=fact。
_RICH_PROPS = {
    "P88": ("委托人", "background"),
    "P180": ("描绘内容", "analysis"),
    "P186": ("材质", "analysis"),
    "P135": ("艺术流派", "significance"),
    "P136": ("题材", "significance"),
    "P1343": ("著录文献", "material"),
}

_RICH_QUERY = """
SELECT ?pid ?vLabel WHERE {{
  VALUES ?prop {{ wdt:P88 wdt:P180 wdt:P186 wdt:P135 wdt:P136 wdt:P1343 }}
  wd:{qid} ?prop ?v .
  ?p wikibase:directClaim ?prop . BIND(STRAFTER(STR(?p), "entity/") AS ?pid)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def _default_run_query(sparql):
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


def fetch_rich_facts(qid: str, *, run_query=None) -> list[dict]:
    """Wikidata 富属性 → 事实原子 [{claim,value,source,topic}]。无→[]。"""
    run_query = run_query or _default_run_query
    rows = run_query(_RICH_QUERY.format(qid=qid))
    out = []
    for row in rows:
        pid = (row.get("pid") or {}).get("value", "")
        val = (row.get("vLabel") or {}).get("value")
        if pid in _RICH_PROPS and val:
            claim, topic = _RICH_PROPS[pid]
            out.append(
                {
                    "claim": claim,
                    "value": val,
                    "source": f"wikidata:{pid}",
                    "topic": topic,
                }
            )
    return out
