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
    return p


def _catalog() -> MuseumCatalog:
    return MuseumCatalog.from_file(CATALOG_PATH)


def cmd_fetch(slug: str) -> None:
    ps = PackStore(get_object_storage())
    fetcher = Fetcher(catalog=_catalog(), sources=[WikidataSource()], pack_store=ps)
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


def main(argv=None) -> None:
    ns = build_parser().parse_args(argv)
    if ns.command == "fetch":
        cmd_fetch(ns.slug)
    else:
        cmd_load(ns.slug, ns.pack, ns.sample, ns.target)


if __name__ == "__main__":
    main()
