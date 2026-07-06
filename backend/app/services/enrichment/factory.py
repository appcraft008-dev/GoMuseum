"""生成组件工厂:onboard generate 与懒生成共用装配(LLM 组件/registry/语言)。"""

from __future__ import annotations

from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[3] / "museums.yaml"


def build_generation_components(slug: str, langs_override=None) -> dict:
    from app.services.enrichment.catalog import MuseumCatalog
    from app.services.enrichment.content_enricher import (
        ContentEnricher,
        default_complete,
    )
    from app.services.enrichment.http_client import PoliteSession
    from app.services.enrichment.lang_config import resolve_languages
    from app.services.enrichment.qa_suggester import QASuggester
    from app.services.enrichment.quality import QualityGate
    from app.services.enrichment.registry import build_registry
    from app.services.enrichment.translator import ContentTranslator

    cfg = MuseumCatalog.from_file(CATALOG_PATH).get(slug)
    gate = QualityGate(default_complete)
    translator = ContentTranslator(
        default_complete,
        complete_strong=lambda s, u: default_complete(s, u, model="gpt-4o"),
    )
    ua = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"
    session = PoliteSession(user_agent=ua, min_interval=1.0)
    return {
        "enricher": ContentEnricher(default_complete),
        "gate": gate,
        "translator": translator,
        "qa_suggester": QASuggester(default_complete, gate, translator),
        "registry": build_registry(cfg.sources, session=session),
        "target_langs": resolve_languages(langs_override or cfg.languages),
        "country_lang": cfg.country_lang,
    }
