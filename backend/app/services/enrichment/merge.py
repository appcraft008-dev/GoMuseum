from __future__ import annotations

from datetime import datetime, timezone

from app.services.enrichment.sources.base import ObjectContribution

# 优先级：越靠后越高。v1 只有 wikidata。
DEFAULT_PRECEDENCE = ["wikidata", "official", "manual"]


def _rank(source: str, precedence: list[str]) -> int:
    return precedence.index(source) if source in precedence else -1


def merge_contributions(
    contribs: list[ObjectContribution],
    precedence: list[str] | None = None,
) -> dict:
    """同一 object 的多源贡献 → canonical dict（含 sources 原始包）。"""
    if not contribs:
        raise ValueError("空贡献")
    precedence = precedence or DEFAULT_PRECEDENCE
    qid = contribs[0].qid
    now = datetime.now(timezone.utc).isoformat()

    canonical: dict = {"qid": qid}
    field_source: dict[str, str] = {}
    sources: dict[str, dict] = {}
    conflicts: list[dict] = []

    for c in sorted(contribs, key=lambda x: _rank(x.source, precedence)):
        sources[c.source] = {"raw": c.raw, "fetched_at": now}
        for k, v in c.fields.items():
            if v is None:
                continue
            prev = canonical.get(k)
            if (
                k in field_source
                and _rank(c.source, precedence) == _rank(field_source[k], precedence)
                and prev != v
            ):
                conflicts.append(
                    {
                        "field": k,
                        "values": [prev, v],
                        "sources": [field_source[k], c.source],
                    }
                )
            canonical[k] = v
            field_source[k] = c.source

    canonical["sources"] = sources
    if conflicts:
        canonical["_conflicts"] = conflicts
    return canonical
