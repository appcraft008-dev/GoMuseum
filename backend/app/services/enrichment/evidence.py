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
    # 关系属性(配源 round2a):给 significance/background 接地影响钩子
    "P4969": ("影响了", "significance"),  # has derivative work
    "P144": ("基于", "background"),  # based on
    "P941": ("受启发于", "background"),  # inspired by
    "P361": ("所属系列", "background"),  # part of
}

_RICH_MAX_PER_PROP = 5  # 多值属性(如衍生作品)每 pid 最多取几条,防名作爆表

_RICH_QUERY = """
SELECT ?pid ?vLabel WHERE {{
  VALUES ?prop {{ wdt:P88 wdt:P180 wdt:P186 wdt:P135 wdt:P136 wdt:P1343
                  wdt:P4969 wdt:P144 wdt:P941 wdt:P361 }}
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
    per_prop: dict[str, int] = {}
    for row in rows:
        pid = (row.get("pid") or {}).get("value", "")
        val = (row.get("vLabel") or {}).get("value")
        if pid in _RICH_PROPS and val:
            if per_prop.get(pid, 0) >= _RICH_MAX_PER_PROP:
                continue  # 每属性限 _RICH_MAX_PER_PROP 条
            per_prop[pid] = per_prop.get(pid, 0) + 1
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


_FLAGGED_SYSTEM = (
    "You are a sourcing analyst. From the MATERIAL, extract ONLY sentences that are NOT "
    "settled fact — i.e. scholarly opinion / interpretation, hedged claims (may, possibly, "
    "believed), disputes, or unverified attributions (e.g. the model's identity). For each, "
    "classify type as one of: contested | inference | unverified. Ignore plain facts. "
    'Return STRICT JSON: {"flagged": [{"text": "...", "type": "..."}]} (empty if none). No commentary.'
)


def _extract_flagged(narrative, complete) -> list:
    text = "\n\n".join(n["text"] for n in narrative if n.get("text"))
    if not text.strip():
        return []
    try:
        from app.services.enrichment.content_enricher import _parse_json

        raw = complete(_FLAGGED_SYSTEM, f"MATERIAL:\n{text}")
        items = _parse_json(raw).get("flagged") or []
        return [
            {
                "text": it["text"],
                "type": it.get("type", "contested"),
                "source": "wikipedia",
            }
            for it in items
            if isinstance(it, dict) and it.get("text")
        ]
    except Exception:
        return []
