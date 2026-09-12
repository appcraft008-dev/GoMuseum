"""JocondeSource：法国国家藏品库(base-joconde-extrait)。
经 Wikidata P347 自动发现；提供权威法语一手事实（source=official）。

⚠️ 2026-09 换过接入方式。原先走 `data.culture.gouv.fr` 的 Opendatasoft API，
文化部 2026-06-01 公告关闭该门户（迁到 data.gouv.fr 生态的 culture.data.gouv.fr），
**但老 API 实际又活到 2026-07-22 才断供**（公告日≠断供日，差 7.5 周）。
断供后旧域任何路径都 301 到新站根、返回 SPA 的 HTML，`get_json` 报"200 但非 JSON"，
被 material.py 的单源容错静默吞掉 —— 整整两个月没人发现。
数据本身没消失：每天更新，只是只剩 data.gouv.fr 上的 CSV，靠表格 API 逐件查。
"""

from __future__ import annotations

from app.services.enrichment.sources.base import ObjectContribution, Source

# 按 slug 取资源 id：文件重传时 id 会变，slug 不会。别硬编码 id。
DATASET_API = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "collections-des-musees-de-france-base-joconde/"
)
TABULAR_URL = "https://tabular-api.data.gouv.fr/api/resources/{rid}/data/"

# 列名 = 旧 Opendatasoft 字段的首字母大写版，一一对应，无字段损失。
_FIELD_MAP = {
    "title_fr": "Titre",
    "artist_fr": "Auteur",
    "medium_fr": "Materiaux_techniques",
    "dimensions": "Mesures",
    "inventory_number": "Numero_inventaire",
    "provenance_fr": "Ancienne_appartenance",
    "exhibitions_fr": "Exposition",
    "bibliography_fr": "Bibliographie",
    "subjects_fr": "Sujet_Represente",
    "period_fr": "Periode_de_creation",
    "domaine_fr": "Domaine",
    "denomination_fr": "Denomination",
    "school_fr": "Ecole_pays",
    "location_fr": "Localisation",
}

_rid_cache: str | None = None


def resolve_resource_id(get_json, *, refresh: bool = False) -> str:
    """CSV 资源 id（进程内缓存一次；逐件富化不该每件都解析一遍）。

    get_json(url, params) -> dict。找不到 CSV 资源 → StopIteration，
    由调用方的单源容错接住（纪律①）。
    """
    global _rid_cache
    if _rid_cache is None or refresh:
        data = get_json(DATASET_API, None)
        _rid_cache = next(
            r["id"] for r in (data.get("resources") or []) if r.get("format") == "csv"
        )
    return _rid_cache


class JocondeSource(Source):
    name = "joconde"

    def __init__(self, session):
        self._session = session  # PoliteSession（注入，复用限速 + 便于测试）

    def probe(self, external_ids: dict) -> bool:
        return "P347" in external_ids

    def enrich(self, qid: str, external_ids: dict, context: dict):
        ref = external_ids.get("P347")
        if not ref:
            return None
        rid = resolve_resource_id(self._session.get_json)
        data = self._session.get_json(
            TABULAR_URL.format(rid=rid), params={"Reference__exact": ref}
        )
        rows = data.get("data") or []
        if not rows:
            return None
        f = rows[0]
        fields = {k: f.get(col) for k, col in _FIELD_MAP.items()}
        return ObjectContribution(
            source="official", qid=qid, fields=fields, raw={"joconde": f}
        )

    def fetch(self, cfg):
        return []
