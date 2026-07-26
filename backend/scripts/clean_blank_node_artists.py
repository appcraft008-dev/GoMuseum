"""清理 blank-node 假作者(2026-07-26 卢浮宫事故)。

Wikidata P170="未知值"(作者不详)返回 blank node
`.well-known/genid/<32位hex>`,旧版 _fetch_creators 把哈希当作者 QID 写进了
objects.attributes.artist_qid,并试图建同名 Artist 行(撞 artists_pkey 崩溃)。

本脚本:①清掉对象上的假 artist_qid ②删掉已建的假 Artist 行(仅无名无 bio 的空壳,
有内容的一律保留人工确认)。幂等,可重跑。

用法: python scripts/clean_blank_node_artists.py [--apply]   # 缺省 dry-run
"""

import re
import sys

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.artist import Artist  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402

_HEX32 = re.compile(r"^[0-9a-f]{32}$")


def main(apply: bool) -> None:
    db = SessionLocal()
    cleaned = 0
    for o in db.query(MuseumObject).all():
        attrs = o.attributes or {}
        aq = attrs.get("artist_qid")
        if aq and _HEX32.match(aq):
            if apply:
                o.attributes = {k: v for k, v in attrs.items() if k != "artist_qid"}
            cleaned += 1
        if apply and cleaned and cleaned % 500 == 0:
            db.commit()
    if apply:
        db.commit()

    dropped = kept = 0
    for a in db.query(Artist).all():
        if not _HEX32.match(a.qid or ""):
            continue
        # 只删空壳;有名字/bio 的保留(不该存在,但宁可留着人工看)
        if a.name_en or a.name_zh or (a.name_i18n or {}) or (a.bio or {}):
            kept += 1
            continue
        if apply:
            db.delete(a)
        dropped += 1
    if apply:
        db.commit()

    mode = "已清理" if apply else "dry-run(加 --apply 生效)"
    print(
        f"{mode}: 对象假 artist_qid={cleaned} | 假 Artist 空壳={dropped} | 保留={kept}"
    )


if __name__ == "__main__":
    main("--apply" in sys.argv)
