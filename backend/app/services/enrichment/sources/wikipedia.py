"""WikipediaSource：按对象各语言 Wikipedia 标题拉正文摘录（叙事接地素材）。
多源语言（en + 馆所在国语言）；用注入的 PoliteSession（限速/缓存）。"""

from __future__ import annotations

from app.services.enrichment.sources.base import ObjectContribution, Source

REST_SUMMARY = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"


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
            data = self._session.get_json(REST_SUMMARY.format(lang=lang, title=title))
            extract = data.get("extract")
            if extract:
                fields[f"extract_{lang}"] = extract
        if not fields:
            return None
        return ObjectContribution(
            source="wikipedia", qid=qid, fields=fields, raw={"titles": titles}
        )

    def fetch(self, cfg):
        return []
