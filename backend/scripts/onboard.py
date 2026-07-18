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
    # views 用 --museum 选馆,故 slug 可选(其余子命令仍靠位置 slug)
    p.add_argument("slug", nargs="?")
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
    ca.add_argument(
        "--source", choices=["wikidata", "joconde"], default="wikidata"
    )  # joconde=补纸上作品(去重只补 Wikidata 缺的件)
    ge = sub.add_parser("generate")
    ge.add_argument("--target", choices=["staging", "prod"], required=True)
    ge.add_argument("--qid", default=None)
    ge.add_argument("--langs", default=None)
    ge.add_argument("--force", action="store_true")
    ge.add_argument("--limit", type=int, default=None)
    ge.add_argument("--allow-full", action="store_true")  # staging 护栏逃生门
    rp = sub.add_parser("report")
    rp.add_argument("--langs", default=None)
    na = sub.add_parser("names")  # 显示名回填(铺目录后即跑;幂等可重跑)
    na.add_argument("--target", choices=["staging", "prod"], required=True)
    na.add_argument("--langs", default=None)
    na.add_argument(
        "--refresh-langs", default=None
    )  # 强刷:该语言权威标签覆盖存量(繁简修复)
    na.add_argument(
        "--retranslate-langs", default=None
    )  # 重译:无权威标签的机翻显示名用改进版重译
    na.add_argument("--limit", type=int, default=None)  # 只处理前 N 件(小样本验证)
    na.add_argument("--allow-full", action="store_true")  # staging 护栏逃生门
    tr = sub.add_parser("translate")  # 补语种:存量对象缺失语言从 en 段纯翻译(幂等)
    tr.add_argument("--target", choices=["staging", "prod"], required=True)
    tr.add_argument("--langs", required=True)  # 如 de,es,it
    tr.add_argument("--limit", type=int, default=None)
    tr.add_argument("--allow-full", action="store_true")  # staging 护栏逃生门
    im = sub.add_parser("images")  # 图像物化:下载→两档→R2→署名(幂等,names 后跑)
    im.add_argument("--target", choices=["staging", "prod"], required=True)
    im.add_argument("--limit", type=int, default=None)
    vw = sub.add_parser("views")  # 雕塑多视角补图(Commons 参考图,物化时嵌入)
    vw.add_argument("--museum", required=True)
    vw.add_argument("--max", type=int, default=4)
    de = sub.add_parser(
        "display-evidence"
    )  # Joconde 展陈证据(法国馆:P347→localisation)
    de.add_argument("--museum", required=True)
    de.add_argument("--limit", type=int, default=None)
    it = sub.add_parser(
        "intro"
    )  # 馆介绍+封面(spec 2026-07-18;门面类预生成,幂等按语言补缺)
    it.add_argument("--target", choices=["staging", "prod"], required=True)
    it.add_argument("--force", action="store_true")
    cr = sub.add_parser("coverage-report")  # 覆盖率报告+museums.stats回写
    cr.add_argument("--museum", required=True)
    cr.add_argument("--json", action="store_true")
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


def cmd_catalog(
    slug: str, target: str, limit: int | None = None, source: str = "wikidata"
) -> None:
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )
    from app.models.museum import Museum
    from app.services.enrichment.catalog_loader import filter_new_stubs, load_stubs
    from app.services.enrichment.identity import merge_stubs

    cfg = _catalog().get(slug)
    if limit:
        from dataclasses import replace

        cfg = replace(cfg, fetch_limit=limit)
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
        if source == "joconde":
            # 补充源:只补 Wikidata 缺的件(去重跳过既有,绝不覆盖既有好数据)
            from app.services.enrichment.sources.joconde_catalog import JocondeCatalog

            stubs = merge_stubs(list(JocondeCatalog().list(cfg)))
            m = db.query(Museum).filter_by(slug=slug).first()
            before = len(stubs)
            stubs = filter_new_stubs(db, m.id if m else None, stubs)
            print(f"  Joconde 列 {before} 件,去重后新增 {len(stubs)} 件")
        else:
            from app.services.enrichment.sources.wikidata_catalog import WikidataCatalog

            stubs = merge_stubs(list(WikidataCatalog().list(cfg)))
        out = load_stubs(db, museum, stubs)
    finally:
        db.close()
    print(f"✓ catalog 落库({source}): {out}")


def cmd_generate(slug, qid, langs, force, limit, target, allow_full=False) -> None:
    from scripts.ops_guard import staging_limit

    limit = staging_limit(target, limit, allow_full)
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


def cmd_names(
    slug: str,
    langs: str | None,
    target: str,
    refresh_langs: str | None = None,
    retranslate_langs: str | None = None,
    limit: int | None = None,
    allow_full: bool = False,
) -> None:
    from scripts.ops_guard import staging_limit

    limit = staging_limit(target, limit, allow_full)
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
            db,
            slug,
            translator=ContentTranslator(
                default_complete,
                complete_strong=lambda s, u: default_complete(s, u, model="gpt-4o"),
            ),
            langs=target_langs,
            refresh_langs=(
                [x.strip() for x in refresh_langs.split(",")] if refresh_langs else None
            ),
            retranslate_langs=(
                [x.strip() for x in retranslate_langs.split(",")]
                if retranslate_langs
                else None
            ),
            limit=limit,
        )
    finally:
        db.close()
    print(f"✓ names 回填完成: {out}")


def cmd_translate(
    slug: str, langs: str, limit: int | None, target: str, allow_full: bool = False
) -> None:
    from scripts.ops_guard import staging_limit

    limit = staging_limit(target, limit, allow_full)
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
            translator=ContentTranslator(
                default_complete,
                complete_strong=lambda s, u: default_complete(s, u, model="gpt-4o"),
            ),
            limit=limit,
        )
    finally:
        db.close()
    print(f"✓ translate 补语种完成: {out}")


def cmd_images(slug: str, limit: int | None, target: str) -> None:
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )
    from app.services.enrichment.materializer import materialize_images

    db = SessionLocal()
    try:
        out = materialize_images(db, slug, limit=limit)
    finally:
        db.close()
    print(f"✓ images 物化完成: {out}")


def cmd_views(museum: str, max_n: int) -> None:
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.views import add_view_images, fetch_view_urls

    db = SessionLocal()
    try:
        m = db.query(Museum).filter_by(slug=museum).one_or_none()
        if not m:
            raise SystemExit(f"❌ 未知博物馆 slug: {museum}")
        objs = (
            db.query(MuseumObject)
            .filter_by(museum_id=m.id, category="sculpture")
            .order_by(MuseumObject.popularity.desc())
            .all()
        )
        total = 0
        for o in objs:
            n = add_view_images(
                db, o, fetch=lambda qid, _room: fetch_view_urls(qid, max_n=max_n)
            )
            db.commit()  # 逐件落盘:中途崩溃不丢已完成件
            total += n
            if n:
                print(f"  {o.qid}: +{n} view(s)")
        print(f"✓ views 补图完成: {len(objs)} 件雕塑, 共新增 {total} 行")
        print(
            "↳ 下一步跑 `images` 物化(下载→R2→自动嵌入): "
            f"python scripts/onboard.py {museum} images --target <env>"
        )
    finally:
        db.close()


def cmd_display_evidence(museum: str, limit: int | None) -> None:
    from app.services.coverage.joconde import enrich_museum_display

    db = SessionLocal()
    try:
        counts = enrich_museum_display(db, museum, limit=limit)
        print(
            f"✓ Joconde 展陈证据: 查 {counts['checked']} 件(有 P347), "
            f"写入 {counts['evidenced']} 件"
        )
    finally:
        db.close()


def cmd_intro(slug: str, target: str, force: bool = False) -> None:
    expected = _ENV_BY_TARGET[target]
    if settings.ENVIRONMENT != expected:
        raise SystemExit(
            f"❌ --target={target} 期望容器 ENVIRONMENT={expected}，"
            f"但当前容器 ENVIRONMENT={settings.ENVIRONMENT}。请在 {expected} 环境容器内运行。"
        )
    from app.services.enrichment.content_enricher import default_complete
    from app.services.enrichment.factory import build_generation_components
    from app.services.enrichment.museum_intro import (
        generate_museum_intro,
        select_cover,
    )

    c = build_generation_components(slug)
    db = SessionLocal()
    try:
        out = generate_museum_intro(
            db,
            slug,
            complete=default_complete,
            gate=c["gate"],
            translator=c["translator"],
            langs=c["target_langs"],  # 馆配置驱动(resolve_languages),不硬编
            force=force,
        )
        cover = select_cover(db, slug, complete=default_complete, force=force)
        db.commit()
    finally:
        db.close()
    print(f"✓ intro: {out} cover={cover}")


def cmd_coverage_report(museum: str, as_json: bool) -> None:
    from scripts.coverage_report import (
        _print_human,
        build_report,
        write_stats,
    )

    db = SessionLocal()
    try:
        report = build_report(db, museum)
        write_stats(db, museum, report)
    finally:
        db.close()
    if as_json:
        import json

        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(museum, report)


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
        cmd_catalog(ns.slug, ns.target, ns.limit, ns.source)
    elif ns.command == "generate":
        cmd_generate(
            ns.slug, ns.qid, ns.langs, ns.force, ns.limit, ns.target, ns.allow_full
        )
    elif ns.command == "report":
        cmd_report(ns.slug, ns.langs)
    elif ns.command == "names":
        cmd_names(
            ns.slug,
            ns.langs,
            ns.target,
            ns.refresh_langs,
            ns.retranslate_langs,
            ns.limit,
            ns.allow_full,
        )
    elif ns.command == "translate":
        cmd_translate(ns.slug, ns.langs, ns.limit, ns.target, ns.allow_full)
    elif ns.command == "images":
        cmd_images(ns.slug, ns.limit, ns.target)
    elif ns.command == "views":
        cmd_views(ns.museum, ns.max)
    elif ns.command == "display-evidence":
        cmd_display_evidence(ns.museum, ns.limit)
    elif ns.command == "intro":
        cmd_intro(ns.slug, ns.target, ns.force)
    elif ns.command == "coverage-report":
        cmd_coverage_report(ns.museum, ns.json)
    else:
        cmd_load(ns.slug, ns.pack, ns.sample, ns.target)


if __name__ == "__main__":
    main()
