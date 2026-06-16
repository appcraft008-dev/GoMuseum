from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.services.enrichment.sources.base import ObjectContribution

logger = logging.getLogger(__name__)

# 优先级：越靠后越高。v1 只有 wikidata。
PRECEDENCE = ["wikidata", "official", "manual"]


def _rank(source: str) -> int:
    return PRECEDENCE.index(source) if source in PRECEDENCE else -1


def merge_contributions(contribs: list[ObjectContribution]) -> dict:
    """同一 object 的多源贡献 → canonical dict（含 sources 原始包）。"""
    if not contribs:
        raise ValueError("空贡献")
    qid = contribs[0].qid
    now = datetime.now(timezone.utc).isoformat()

    canonical: dict = {"qid": qid}
    field_source: dict[str, str] = {}
    sources: dict[str, dict] = {}

    for c in sorted(contribs, key=lambda x: _rank(x.source)):  # 低→高，高的后写覆盖
        sources[c.source] = {"raw": c.raw, "fetched_at": now}
        for k, v in c.fields.items():
            if v is None:
                continue
            if k in field_source and _rank(c.source) == _rank(field_source[k]):
                logger.warning("字段冲突 qid=%s field=%s 同级源", qid, k)
            canonical[k] = v
            field_source[k] = c.source

    canonical["sources"] = sources
    return canonical
