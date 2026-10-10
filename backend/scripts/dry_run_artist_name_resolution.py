"""只读 dry-run:在奥赛+橘园全馆跑一遍 resolve_creator_by_name,打印会解析
出什么,不写库。人工过一遍输出,确认没有明显张冠李戴,再决定要不要正式
跑存量回填(spec §4:存量回填本身不在这次设计范围,这个脚本只是验证新
函数在真实规模数据上的表现)。

用法(需要在能连 prod 只读副本或 prod 容器内跑,示例假设已有 DB session):
    python scripts/dry_run_artist_name_resolution.py --slug orsay
    python scripts/dry_run_artist_name_resolution.py --slug orangerie
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.enrichment.material import resolve_creator_by_name

# 礼貌限速:resolve_creator_by_name 本身不带限速(单件懒生成场景下一次最多
# 几次请求,不需要),但这里是批量扫一整个馆(奥赛 1628 件),不加限速会在
# 短时间内对 Wikidata 发出大量请求。
_SLEEP_SECONDS = 0.3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        m = db.query(Museum).filter_by(slug=args.slug).one()
        objs = (
            db.query(MuseumObject)
            .filter_by(museum_id=m.id)
            .filter(MuseumObject.artist_en.isnot(None))
            .all()
        )
        resolved = skipped_has_aqid = skipped_qid_format = abstained = 0
        for o in objs:
            attrs = o.attributes or {}
            if attrs.get("artist_qid"):
                skipped_has_aqid += 1
                continue
            if o.qid.startswith("Q"):
                skipped_qid_format += 1
                continue
            aqid = resolve_creator_by_name(o.artist_en)
            time.sleep(_SLEEP_SECONDS)
            if aqid:
                resolved += 1
                print(f"RESOLVED\t{o.qid}\t{o.artist_en!r}\t-> {aqid}")
            else:
                abstained += 1
                print(f"ABSTAIN \t{o.qid}\t{o.artist_en!r}")
        print(
            f"\n--- {args.slug} 汇总 ---\n"
            f"resolved={resolved} abstained={abstained} "
            f"skipped(已有artist_qid)={skipped_has_aqid} "
            f"skipped(Wikidata qid)={skipped_qid_format}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
