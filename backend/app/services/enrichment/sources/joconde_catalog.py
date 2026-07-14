"""JocondeCatalog：从 data.culture.gouv.fr(Joconde 开放数据)列该馆全部作品 → StubRecord。
补 Wikidata 对纸上作品(粉彩/素描)的覆盖偏科(实证:Wikidata 收奥赛纸上仅 167,
Joconde 有 434 素描)。多为 © RMN 版权图、无免费图 → 落文字层 stub(可搜、不可拍)。
去重靠 Joconde reference(P347)+ 馆藏号,不覆盖既有 Wikidata 件(见 catalog_loader.filter_new_stubs)。"""

from __future__ import annotations

import re
import time
from typing import Iterable

from app.services.enrichment.catalog_source import CatalogSource, StubRecord

_RECORDS_URL = (
    "https://data.culture.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "base-joconde-extrait/records"
)
_UA = "GoMuseumEnrichment/1.0 (appcraft008@gmail.com)"
_SELECT = (
    "reference",
    "numero_inventaire",
    "titre",
    "auteur",
    "domaine",
    "millesime_de_creation",
)
_PAGE = 100  # Opendatasoft 单页上限
_MAX_OFFSET = 9900  # limit+offset ≤ 10000 的保护

_DATES = re.compile(r"\s*\([^)]*\)\s*$")  # 作者尾部"(1844-1926)"
_DOMAINE_CAT = {
    "peinture": "painting",
    "sculpture": "sculpture",
    "dessin": "works_on_paper",
    "estampe": "works_on_paper",
    "aquarelle": "works_on_paper",
    "pastel": "works_on_paper",
    "photographie": "photography",
}


def _clean_inv(raw: str | None) -> str | None:
    """取首个馆藏号:'RF 2051, recto'→'RF 2051';'RF 1977 444 ; LUX 1051 P'→'RF 1977 444'
    (多号/recto-verso 后缀切掉,取第一个;否则整串归一化后与 Wikidata 号对不上、去重失效)。"""
    if not raw:
        return None
    return re.split(r"[;,]", raw)[0].strip() or None


def _clean_artist(raw: str | None) -> str | None:
    """'Cassatt Mary (1844-1926)' → 'Cassatt Mary'(去生卒;姓名序保留源样,不冒险重排)。"""
    if not raw:
        return None
    return _DATES.sub("", raw).strip() or None


def _clean_title(raw: str | None) -> str | None:
    """取首个题名(去' OU 别名'/'; dit aussi');Joconde 全大写 → 句首大写。
    en 列存法文题,names 回填时机翻补多语显示名(同无 qid 冷门件路径)。"""
    if not raw:
        return None
    t = re.split(r"\s+OU\s+", raw, maxsplit=1)[0]
    t = t.split(" ; ")[0].strip()
    if t.isupper():
        t = t.capitalize()
    return t or None


def _category(domaine) -> str:
    for d in domaine or []:
        c = _DOMAINE_CAT.get(str(d).lower())
        if c:
            return c
    return "unknown"


def _to_stub(rec: dict, slug: str) -> StubRecord | None:
    """一条 Joconde 记录 → StubRecord。无馆藏号(无法幂等去重/落库)→ None。"""
    inv = _clean_inv(rec.get("numero_inventaire"))
    if not inv:
        return None
    ref = rec.get("reference")
    return StubRecord(
        inventory_number=inv,
        qid=None,
        title=_clean_title(rec.get("titre")),
        artist=_clean_artist(rec.get("auteur")),
        year=rec.get("millesime_de_creation"),
        category=_category(rec.get("domaine")),
        image_url=None,  # © RMN 版权图,无免费图 → 文字层
        popularity=0,
        owning_museum=slug,
        source="joconde",
        raw={"reference": ref},
        external_ids={"P347": ref} if ref else {},
    )


def _default_http_get(url, params=None, headers=None, timeout=None):
    import requests

    time.sleep(0.2)  # 礼貌限速(公共开放数据)
    return requests.get(url, params=params, headers=headers, timeout=timeout)


class JocondeCatalog(CatalogSource):
    name = "joconde"

    def __init__(self, http_get=None):
        self._http_get = http_get or _default_http_get

    def list(self, cfg) -> Iterable[StubRecord]:
        museum = getattr(cfg, "joconde_museum", None)
        if not museum:
            return
        offset = 0
        while offset <= _MAX_OFFSET:
            resp = self._http_get(
                _RECORDS_URL,
                params={
                    "where": f'nom_officiel_musee="{museum}"',
                    "select": ",".join(_SELECT),
                    "limit": _PAGE,
                    "offset": offset,
                },
                headers={"User-Agent": _UA, "Accept": "application/json"},
                timeout=30,
            )
            if getattr(resp, "status_code", 200) != 200:
                break
            results = (resp.json() or {}).get("results") or []
            if not results:
                break
            for rec in results:
                s = _to_stub(rec, cfg.slug)
                if s:
                    yield s
            offset += len(results)
            if len(results) < _PAGE:
                break
