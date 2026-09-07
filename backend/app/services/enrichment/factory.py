"""生成组件工厂:onboard generate 与懒生成共用装配(LLM 组件/registry/语言)。"""

from __future__ import annotations

from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[3] / "museums.yaml"


def build_translator(channel: str = "translate"):
    """ContentTranslator 的**唯一**构造入口。

    别在调用点各拼一个 —— 这段装配曾原样复制在 4 处(factory / lazy / onboard×2),
    于是 PR #430 给忠实度闸接确定性通道时只改到了 1 处,另外 3 条路径(懒生成、
    onboard names、onboard translate)照旧用 temperature=0.3 判定,而单测全绿。
    构造分散 = 下次加参数还会漏,所以收敛成一个函数,不是补三个补丁。
    """
    from app.services.enrichment.content_enricher import default_complete
    from app.services.enrichment.translator import ContentTranslator

    return ContentTranslator(
        lambda s, u, model="gpt-4o-mini": default_complete(
            s, u, model, channel=channel
        ),
        complete_strong=lambda s, u: default_complete(
            s, u, model="gpt-4o", channel=channel
        ),
        # 判定要可复现,不能跟着翻译一起随机(契约纪律 27)
        complete_judge=lambda s, u, model="gpt-4o-mini": default_complete(
            s, u, model, channel=channel, temperature=0
        ),
    )


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

    def _tagged(channel, temperature=0.3):
        """用量记账通路打标(成本工程①):同一 default_complete,只多 channel 标签。

        temperature=0 的两个通路是**判定**(接地闸、译文忠实闸),不是创作 —— 见
        default_complete 的 docstring:0.3 会让同一条内容重跑给出不同结论(实测 13.3%)。
        """
        return lambda s, u, model="gpt-4o-mini": default_complete(
            s, u, model, channel=channel, temperature=temperature
        )

    cfg = MuseumCatalog.from_file(CATALOG_PATH).get(slug)
    gate = QualityGate(_tagged("gate", temperature=0))
    translator = build_translator("translate")
    ua = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"
    session = PoliteSession(user_agent=ua, min_interval=1.0)
    return {
        # probe 走独立通路 + temperature=0:料探针是判定,不是生成(见 ContentEnricher)
        "enricher": ContentEnricher(
            _tagged("generate"), probe_complete=_tagged("probe", temperature=0)
        ),
        "gate": gate,
        "translator": translator,
        "qa_suggester": QASuggester(_tagged("qa"), gate, translator),
        "registry": build_registry(cfg.sources, session=session),
        "target_langs": resolve_languages(langs_override or cfg.languages),
        "country_lang": cfg.country_lang,
        "intro_qid": cfg.intro_qid,
    }
