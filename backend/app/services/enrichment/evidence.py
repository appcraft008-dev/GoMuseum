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


# Joconde/基础 attributes 键 → (claim, topic, tier)。wall_label=进面板, material=只喂生成。
_ATTR_FACTS = {
    "medium_fr": ("材质", "analysis", "wall_label"),
    "dimensions": ("尺寸", "analysis", "wall_label"),
    "inventory_number": ("馆藏号", "background", "wall_label"),
    "subjects_fr": ("主题", "analysis", "material"),
    "provenance_fr": ("来源流转", "background", "material"),
    "exhibitions_fr": ("展览史", "background", "material"),
    "bibliography_fr": ("参考文献", "material", "material"),
    "period_fr": ("创作时期", "background", "material"),
    "school_fr": ("流派国别", "significance", "material"),
}

_OBJ_FACTS = [
    ("艺术家", "artist_en", "artist", "wall_label"),
    ("年代", "year", "background", "wall_label"),
    ("标题", "title_en", "background", "wall_label"),
]


def build_evidence_pack(obj: dict, *, run_query=None, complete=None) -> dict:
    """组装证据包:结构原子 facts(带 tier)+ 标源 narrative + (可选)LLM flagged。"""
    attrs = obj.get("attributes") or {}
    facts = []
    for claim, key, topic, tier in _OBJ_FACTS:
        if obj.get(key):
            facts.append(
                {
                    "claim": claim,
                    "value": obj[key],
                    "source": f"object:{key}",
                    "topic": topic,
                    "tier": tier,
                }
            )
    for key, (claim, topic, tier) in _ATTR_FACTS.items():
        if attrs.get(key):
            facts.append(
                {
                    "claim": claim,
                    "value": attrs[key],
                    "source": f"joconde:{key}",
                    "topic": topic,
                    "tier": tier,
                }
            )
    if obj.get("qid"):
        try:
            for f in fetch_rich_facts(obj["qid"], run_query=run_query):
                f.setdefault("tier", "material")
                facts.append(f)
        except Exception:
            pass  # 富属性/网络失败不拖垮
    narrative = []
    for key, src in [
        ("extract_en", "wikipedia:work"),
        ("extract_fr", "wikipedia:work"),
        ("artist_extract_en", "wikipedia:artist"),
        ("artist_extract_fr", "wikipedia:artist"),
    ]:
        if attrs.get(key):
            narrative.append({"text": attrs[key], "source": src, "type": "mainstream"})
    flagged = _extract_flagged(narrative, complete) if complete else []
    return {"facts": facts, "narrative": narrative, "flagged": flagged}


def _extract_flagged(narrative, complete) -> list:
    return []  # 下一任务实现
