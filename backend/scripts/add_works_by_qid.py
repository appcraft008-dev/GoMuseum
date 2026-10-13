"""按 qid 补收录目录里漏掉的在展件(P2-11):Wikidata 没挂本馆 P195,catalog 永远列不到。

复用 catalog 同一条 SPARQL(只把「按馆藏列」换成「指定 qid」)→ load_stubs → 只回填这几件的
显示名 → 逐件物化图片(含识别向量)。正文走懒生成。
Wikidata 无 P18 时可用 --image 指定 Commons 文件(需自由授权)。默认 dry-run。

  python scripts/add_works_by_qid.py louvre Q28792214
  python scripts/add_works_by_qid.py orsay Q140606109 --image "File.jpg" --category sculpture
  ... --apply
"""

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.enrichment.sources import wikidata as _wd  # noqa: E402
from app.services.enrichment.sources.wikidata_catalog import (  # noqa: E402
    WikidataCatalog,
)
from scripts.onboard import _catalog  # noqa: E402

_FILEPATH = (
    "http://commons.wikimedia.org/wiki/Special:FilePath/"  # 与 SPARQL 的 P18 同形
)


def stubs_for(cfg, qids, image=None, category=None):
    # 指定 qid 就是要收它,不按馆的 P31 类目白名单过滤(Q140606109 的 P31 误填成「白色大理石」)
    cfg = replace(cfg, collect_all_types=True)
    anchor = "?item wdt:P195 ?mus ."
    assert anchor in _wd.QUERY, "catalog SPARQL 改了,同步这里"
    values = "VALUES ?item { " + " ".join(f"wd:{q}" for q in qids) + " } ."
    out = list(
        WikidataCatalog(
            run_query=lambda s: _wd.run_sparql(s.replace(anchor, values))
        ).list(cfg)
    )
    for s in out:
        s.owning_museum = cfg.slug
        if category:
            s.category = category
        if image and not s.image_urls:
            s.image_url = _FILEPATH + quote(image)
            s.image_urls = [s.image_url]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("qids", nargs="+")
    ap.add_argument("--image", help="Wikidata 无 P18 时用的 Commons 文件名(仅单 qid)")
    ap.add_argument("--category", help="Wikidata P31 填错时手工指定(如 sculpture)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    assert not a.image or len(a.qids) == 1
    cfg = _catalog().get(a.slug)
    stubs = stubs_for(cfg, a.qids, a.image, a.category)
    for s in stubs:
        print(
            s.qid,
            s.title,
            "|",
            s.artist,
            "|",
            s.inventory_number,
            "|",
            s.category,
            "|",
            s.image_urls,
        )
    missing = set(a.qids) - {s.qid for s in stubs}
    if missing:
        sys.exit(f"Wikidata 没取到(类目过滤或查询失败):{missing}")
    if not a.apply:
        print("DRY-RUN")
        return
    from app.core.database import SessionLocal
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.backfill import backfill_display_names
    from app.services.enrichment.catalog_loader import load_stubs
    from app.services.enrichment.factory import build_translator
    from app.services.enrichment.lang_config import resolve_languages
    from app.services.enrichment.materializer import materialize_object_images

    db = SessionLocal()
    try:
        museum = {  # 与 onboard cmd_catalog 同
            "slug": cfg.slug,
            "qid": cfg.wikidata_qid,
            "name_zh": cfg.name_zh,
            "name_en": cfg.name_en,
            "city_zh": cfg.city_zh,
            "city_en": cfg.city_en,
            "country": cfg.country,
        }
        print("catalog:", load_stubs(db, museum, stubs))
        names = backfill_display_names(
            db,
            cfg.slug,
            translator=build_translator("names"),
            langs=resolve_languages(cfg.languages),
            qids=a.qids,
        )
        print("names:", names)
        for qid in a.qids:  # 物化=下载→R2→嵌入向量(识别要的就是这个)
            o = db.query(MuseumObject).filter_by(qid=qid).one()
            print(qid, "images:", materialize_object_images(db, o))
            db.commit()
    finally:
        db.close()
    print("内容走懒生成(游客首次打开时生成)")


if __name__ == "__main__":
    main()
