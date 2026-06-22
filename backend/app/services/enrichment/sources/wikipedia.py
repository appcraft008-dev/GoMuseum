"""WikipediaSource：按对象各语言 Wikipedia 标题拉**全文** plaintext（叙事接地素材，有界）。
多源语言（en + 馆所在国语言）；用注入的 PoliteSession（限速/缓存/UA）。"""

from __future__ import annotations

from app.services.enrichment.sources.base import ObjectContribution, Source

API = "https://{lang}.wikipedia.org/w/api.php"
MAX_EXTRACT_CHARS = (
    5000  # 全文截断上限：控 grounding prompt 成本/噪声；正文实质内容前置
)


class WikipediaSource(Source):
    name = "wikipedia"

    def __init__(self, session):
        self._session = session

    def enrich(self, qid: str, external_ids: dict, context: dict):
        titles = (context or {}).get("wiki_titles") or {}
        if not titles:
            return None
        fields = {}
        for lang, title in titles.items():
            data = self._session.get_json(
                API.format(lang=lang),
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "extracts",
                    "explaintext": 1,
                    "exsectionformat": "plain",
                    "redirects": 1,
                    "titles": title,
                },
            )
            pages = ((data or {}).get("query") or {}).get("pages") or {}
            extract = ""
            for pg in pages.values():
                extract = pg.get("extract") or ""
                break
            if extract:
                fields[f"extract_{lang}"] = extract[:MAX_EXTRACT_CHARS]
        if not fields:
            return None
        return ObjectContribution(
            source="wikipedia", qid=qid, fields=fields, raw={"titles": titles}
        )

    def fetch(self, cfg):
        return []
