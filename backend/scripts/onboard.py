"""上馆 CLI：fetch（抓→R2 pack）/ load（pack→DB，staging 样本/prod 全量）。

用法：
  python scripts/onboard.py <slug> fetch
  python scripts/onboard.py <slug> load --target staging --pack <key> --sample
  python scripts/onboard.py <slug> load --target prod    --pack <key>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.enrichment.catalog import MuseumCatalog  # noqa: E402
from app.services.enrichment.fetcher import Fetcher  # noqa: E402
from app.services.enrichment.loader import load, select_sample  # noqa: E402
from app.services.enrichment.pack_store import PackStore  # noqa: E402
from app.services.enrichment.report import build_report  # noqa: E402
from app.services.enrichment.sources.wikidata import WikidataSource  # noqa: E402
from app.services.storage import get_object_storage  # noqa: E402

CATALOG_PATH = Path(__file__).resolve().parents[1] / "museums.yaml"

# --target → 期望的容器 ENVIRONMENT；load 在哪个 DB 取决于在哪个容器跑（SessionLocal
# 用容器自身 DATABASE_URL），故用 ENVIRONMENT 守卫，防在错环境的容器里误执行。
_ENV_BY_TARGET = {"prod": "production", "staging": "staging"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="上馆富化管线")
    p.add_argument("slug")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch")
    lo = sub.add_parser("load")
    lo.add_argument("--target", choices=["staging", "prod"], required=True)
    lo.add_argument("--pack", default=None)
    lo.add_argument("--sample", action="store_true")
    ca = sub.add_parser("catalog")
    ca.add_argument("--target", choices=["staging", "prod"], required=True)
    ge = sub.add_parser("generate")
    ge.add_argument("--target", choices=["staging", "prod"], required=True)
    ge.add_argument("--qid", default=None)
    ge.add_argument("--langs", default=None)
    ge.add_argument("--force", action="store_true")
    ge.add_argument("--limit", type=int, default=None)
    rp = sub.add_parser("report")
    rp.add_argument("--langs", default=None)
    return p


def _catalog() -> MuseumCatalog:
    return MuseumCatalog.from_file(CATALOG_PATH)


def cmd_fetch(slug: str) -> None:
    from app.services.enrichment.http_client import PoliteSession
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.joconde import JocondeSource
    from app.services.enrichment.sources.wikipedia import WikipediaSource

    ua = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"
    session = PoliteSession(user_agent=ua, min_interval=1.0)
    ps = PackStore(get_object_storage())
    spine = WikidataSource()
    registry = SourceRegistry(
        [JocondeSource(session=session), WikipediaSource(session=session)]
    )
    fetcher = Fetcher(catalog=_catalog(), spine=spine, registry=registry, pack_store=ps)
    key = fetcher.fetch(slug)
    print(f"✓ pack 已写入: {key}")


def cmd_load(slug: str, pack_key: str, sample: bool, target: str) -> None:
    # 守卫：--target 必须匹配当前容器的 ENVIRONMENT，否则可能误把 prod 数据灌进 staging（反之亦然）
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。"
            f"请在 {expected} 环境的容器内运行此命令。"
        )
    ps = PackStore(get_object_storage())
    if not pack_key:
        raise SystemExit("请用 --pack <key> 指定 pack")
    pack = ps.get(pack_key)
    if sample:
        cfg = _catalog().get(slug)
        pack["_sample"] = {"size": cfg.sample_size, "qids": cfg.sample_qids}
    db = SessionLocal()
    try:
        n = load(db, pack, sample=sample)
    finally:
        db.close()
    print(f"✓ 入库 {n} 件 (sample={sample})")
    if sample:
        # 报告反映实际灌入 staging 的样本（与 loader 同一筛选逻辑），而非全量
        reported = select_sample(
            pack["objects"], pack["_sample"]["size"], pack["_sample"]["qids"]
        )
        print(build_report(slug, reported, as_markdown=True))


def cmd_catalog(slug: str, target: str) -> None:
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )
    from app.services.enrichment.catalog_loader import load_stubs
    from app.services.enrichment.identity import merge_stubs
    from app.services.enrichment.sources.wikidata_catalog import WikidataCatalog

    cfg = _catalog().get(slug)
    stubs = merge_stubs(list(WikidataCatalog().list(cfg)))
    museum = {
        "slug": cfg.slug,
        "qid": cfg.wikidata_qid,
        "name_zh": cfg.name_zh,
        "name_en": cfg.name_en,
        "city_zh": cfg.city_zh,
        "city_en": cfg.city_en,
        "country": cfg.country,
    }
    db = SessionLocal()
    try:
        out = load_stubs(db, museum, stubs)
    finally:
        db.close()
    print(f"✓ catalog 落库: {out}")


def cmd_generate(slug, qid, langs, force, limit, target) -> None:
    # 守卫：--target 必须匹配当前容器 ENVIRONMENT（与 cmd_load 同，先于构造 LLM 组件）
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )

    from app.services.enrichment.content_enricher import (
        ContentEnricher,
        default_complete,
    )
    from app.services.enrichment.lang_config import resolve_languages
    from app.services.enrichment.pipeline import generate_museum, generate_object
    from app.services.enrichment.qa_suggester import QASuggester
    from app.services.enrichment.quality import QualityGate
    from app.services.enrichment.translator import ContentTranslator

    override = (
        [s.strip() for s in langs.split(",")]
        if langs
        else _catalog().get(slug).languages
    )
    target_langs = resolve_languages(override)
    enricher = ContentEnricher(default_complete)
    gate = QualityGate(default_complete)
    translator = ContentTranslator(default_complete)
    qa_suggester = QASuggester(default_complete, gate, translator)

    from app.services.enrichment.http_client import PoliteSession
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.joconde import JocondeSource
    from app.services.enrichment.sources.wikipedia import WikipediaSource

    ua = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"
    session = PoliteSession(user_agent=ua, min_interval=1.0)
    registry = SourceRegistry(
        [JocondeSource(session=session), WikipediaSource(session=session)]
    )

    db = SessionLocal()
    try:
        if qid:
            out = generate_object(
                db,
                qid,
                enricher=enricher,
                gate=gate,
                translator=translator,
                target_langs=target_langs,
                model="gpt-4o-mini",
                force=force,
                qa_suggester=qa_suggester,
                registry=registry,
            )
        else:
            out = generate_museum(
                db,
                slug,
                enricher=enricher,
                gate=gate,
                translator=translator,
                target_langs=target_langs,
                model="gpt-4o-mini",
                force=force,
                limit=limit,
                qa_suggester=qa_suggester,
                registry=registry,
            )
    finally:
        db.close()
    print(f"✓ generate 完成: {out}")


def cmd_report(slug: str, langs: str | None) -> None:
    from app.services.enrichment.content_report import build_quality_report
    from app.services.enrichment.lang_config import resolve_languages

    override = (
        [s.strip() for s in langs.split(",")]
        if langs
        else _catalog().get(slug).languages
    )
    target_langs = resolve_languages(override)
    db = SessionLocal()
    try:
        print(build_quality_report(db, slug, target_langs, as_markdown=True))
    finally:
        db.close()


def main(argv=None) -> None:
    ns = build_parser().parse_args(argv)
    if ns.command == "fetch":
        cmd_fetch(ns.slug)
    elif ns.command == "catalog":
        cmd_catalog(ns.slug, ns.target)
    elif ns.command == "generate":
        cmd_generate(ns.slug, ns.qid, ns.langs, ns.force, ns.limit, ns.target)
    elif ns.command == "report":
        cmd_report(ns.slug, ns.langs)
    else:
        cmd_load(ns.slug, ns.pack, ns.sample, ns.target)


if __name__ == "__main__":
    main()
