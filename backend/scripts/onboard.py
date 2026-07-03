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
    ca.add_argument(
        "--limit", type=int, default=None
    )  # 覆盖 fetch_limit(staging 小样本)
    ge = sub.add_parser("generate")
    ge.add_argument("--target", choices=["staging", "prod"], required=True)
    ge.add_argument("--qid", default=None)
    ge.add_argument("--langs", default=None)
    ge.add_argument("--force", action="store_true")
    ge.add_argument("--limit", type=int, default=None)
    rp = sub.add_parser("report")
    rp.add_argument("--langs", default=None)
    na = sub.add_parser("names")  # 显示名回填(铺目录后即跑;幂等可重跑)
    na.add_argument("--target", choices=["staging", "prod"], required=True)
    na.add_argument("--langs", default=None)
    tr = sub.add_parser("translate")  # 补语种:存量对象缺失语言从 en 段纯翻译(幂等)
    tr.add_argument("--target", choices=["staging", "prod"], required=True)
    tr.add_argument("--langs", required=True)  # 如 de,es,it
    tr.add_argument("--limit", type=int, default=None)
    return p


def _catalog() -> MuseumCatalog:
    return MuseumCatalog.from_file(CATALOG_PATH)


def _registry(slug: str):
    """按馆配置 sources 组 registry（礼貌限速 session 共享）。"""
    from app.services.enrichment.http_client import PoliteSession
    from app.services.enrichment.registry import build_registry

    ua = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"
    session = PoliteSession(user_agent=ua, min_interval=1.0)
    return build_registry(_catalog().get(slug).sources, session=session)


def cmd_fetch(slug: str) -> None:
    ps = PackStore(get_object_storage())
    spine = WikidataSource()
    fetcher = Fetcher(
        catalog=_catalog(), spine=spine, registry=_registry(slug), pack_store=ps
    )
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


def cmd_catalog(slug: str, target: str, limit: int | None = None) -> None:
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
    if limit:
        from dataclasses import replace

        cfg = replace(cfg, fetch_limit=limit)
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

    from app.services.enrichment.factory import build_generation_components
    from app.services.enrichment.pipeline import generate_museum, generate_object

    override = [s.strip() for s in langs.split(",")] if langs else None
    c = build_generation_components(slug, langs_override=override)
    common = dict(
        enricher=c["enricher"],
        gate=c["gate"],
        translator=c["translator"],
        target_langs=c["target_langs"],
        model="gpt-4o-mini",
        force=force,
        qa_suggester=c["qa_suggester"],
        registry=c["registry"],
        country_lang=c["country_lang"],
    )
    db = SessionLocal()
    try:
        if qid:
            out = generate_object(db, qid, **common)
        else:
            out = generate_museum(db, slug, limit=limit, **common)
    finally:
        db.close()
    print(f"✓ generate 完成: {out}")


def cmd_names(slug: str, langs: str | None, target: str) -> None:
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )
    from app.services.enrichment.backfill import backfill_display_names
    from app.services.enrichment.content_enricher import default_complete
    from app.services.enrichment.lang_config import resolve_languages
    from app.services.enrichment.translator import ContentTranslator

    cfg = _catalog().get(slug)
    override = [s.strip() for s in langs.split(",")] if langs else cfg.languages
    target_langs = resolve_languages(override)
    db = SessionLocal()
    try:
        out = backfill_display_names(
            db, slug, translator=ContentTranslator(default_complete), langs=target_langs
        )
    finally:
        db.close()
    print(f"✓ names 回填完成: {out}")


def cmd_translate(slug: str, langs: str, limit: int | None, target: str) -> None:
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )
    from app.services.enrichment.backfill import backfill_languages
    from app.services.enrichment.content_enricher import default_complete
    from app.services.enrichment.translator import ContentTranslator

    db = SessionLocal()
    try:
        out = backfill_languages(
            db,
            slug,
            langs=[s.strip() for s in langs.split(",")],
            translator=ContentTranslator(default_complete),
            limit=limit,
        )
    finally:
        db.close()
    print(f"✓ translate 补语种完成: {out}")


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
        cmd_catalog(ns.slug, ns.target, ns.limit)
    elif ns.command == "generate":
        cmd_generate(ns.slug, ns.qid, ns.langs, ns.force, ns.limit, ns.target)
    elif ns.command == "report":
        cmd_report(ns.slug, ns.langs)
    elif ns.command == "names":
        cmd_names(ns.slug, ns.langs, ns.target)
    elif ns.command == "translate":
        cmd_translate(ns.slug, ns.langs, ns.limit, ns.target)
    else:
        cmd_load(ns.slug, ns.pack, ns.sample, ns.target)


if __name__ == "__main__":
    main()
