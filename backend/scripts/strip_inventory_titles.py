"""存量修复:显示名尾部混入的**本件馆藏号**「statue (Ma 2223)」「Lion head-E 2558」。

根因已在 strip_inventory(铺目录/names 两条路进库前剥)修;这里一次性清存量。
只写 museum_objects 的 title_i18n + title_en/title_zh 三处,不碰正文/问答/音频。
判据同 strip_inventory:与本件 inventory_number 归一化相等且在尾部才剥。

用法(容器内):
    python scripts/strip_inventory_titles.py           # dry-run,打印样例与计数
    python scripts/strip_inventory_titles.py --apply   # 先 R2 快照再写
幂等。
"""

import argparse
import sys

sys.path.insert(0, "/app")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.enrichment.backfill import strip_inventory  # noqa: E402
from scripts.ops_guard import write_surface_and_snapshot  # noqa: E402


def plan(o):
    """→ (新 title_i18n 或 None, {列: 新值}),没变化返回 (None, {})。"""
    inv = o.inventory_number
    ti = (o.attributes or {}).get("title_i18n") or {}
    new_ti = {k: strip_inventory(v, inv) if v else v for k, v in ti.items()}
    cols = {
        c: strip_inventory(getattr(o, c), inv)
        for c in ("title_en", "title_zh")
        if getattr(o, c) and strip_inventory(getattr(o, c), inv) != getattr(o, c)
    }
    return (new_ti if new_ti != ti else None), cols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    objs = (
        db.query(MuseumObject)
        .filter(MuseumObject.inventory_number.isnot(None))
        .filter(MuseumObject.inventory_number != "")
        .all()
    )
    todo = [(o, *plan(o)) for o in objs]
    todo = [t for t in todo if t[1] is not None or t[2]]
    n_titles = sum(
        sum(1 for k, v in (ti or {}).items() if v != o.attributes["title_i18n"][k])
        + len(cols)
        for o, ti, cols in todo
    )
    ready = [o.qid for o, _, _ in todo if o.content_status == "ready"]
    for o, ti, cols in todo[:15]:
        old = (o.attributes or {}).get("title_i18n") or {}
        for k in sorted(ti or {}):
            if ti[k] != old[k]:
                print(f"{o.qid} {k}: {old[k]!r} -> {ti[k]!r}")
        for c, v in cols.items():
            print(f"{o.qid} col {c}: {getattr(o, c)!r} -> {v!r}")
    print(f"objects {len(todo)}  titles {n_titles}  ready {len(ready)} {ready}")
    if not a.apply:
        print("DRY-RUN")
        return
    print(
        write_surface_and_snapshot(
            db, "strip_inventory_titles", [o.id for o, _, _ in todo]
        )
    )
    for o, ti, cols in todo:
        if ti is not None:
            o.attributes = {**o.attributes, "title_i18n": ti}
            flag_modified(o, "attributes")
        for c, v in cols.items():
            setattr(o, c, v)
    db.commit()
    print("APPLIED")


if __name__ == "__main__":
    main()
