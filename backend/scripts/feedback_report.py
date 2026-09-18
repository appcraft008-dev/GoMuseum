"""用户反馈报告(2026-09-18)。

**不建后台** —— 沿用 ops_report / llm_cost_report 的模式:一条命令一屏输出。
没有读反馈的路径,收反馈这件事就是白做的。

🔑 **计数数的是不同 device_id 的个数,不是行数。**
双击提交、或"请求其实已到达但客户端超时、用户点了重试",都会造重复行。
而这份报告的全部用处是「第三个人报同一件事就浮上来」—— 要的是**多少人报过**。
去重放在读侧比写侧加幂等键更省、也更准。

⚠️ `content_wrong` 类别先看一眼是不是**名字回退**再动正文:
用户在 zh-hant 页面看到作者名显示成英文,那是 `museum_repo.py::_resolve_name`
的正常回退(缺 zh-hant 就回退英文),缺的是 `artist.name_i18n` 的 zh-hant 支,
**不在 object_content_sections 那一行里**。坐标"对得上语言"不等于"对得上出错的表"。

用法(容器内):
  python scripts/feedback_report.py [--days 30] [--json]
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from sqlalchemy import func  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.feedback import Feedback  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402


def _since(days: int):
    return datetime.now(timezone.utc) - timedelta(days=days)


def build(db, days: int, limit: int = 20) -> dict:
    since = _since(days)
    base = db.query(Feedback).filter(Feedback.created_at >= since)

    # 一个 device_id 在同一 (qid, language, kind) 上报多少次都只算一个人。
    reporters = func.count(func.distinct(Feedback.device_id))

    by_object = (
        base.with_entities(
            Feedback.qid,
            Feedback.language,
            Feedback.kind,
            reporters.label("people"),
            func.count(Feedback.id).label("rows"),
        )
        .filter(Feedback.scope == "object")
        .group_by(Feedback.qid, Feedback.language, Feedback.kind)
        .order_by(reporters.desc())
        .limit(limit)
        .all()
    )

    titles = {}
    qids = [r.qid for r in by_object if r.qid]
    if qids:
        titles = dict(
            db.query(MuseumObject.qid, MuseumObject.title_en).filter(
                MuseumObject.qid.in_(qids)
            )
        )

    by_app = (
        base.with_entities(
            Feedback.kind,
            Feedback.app_version,
            reporters.label("people"),
            func.count(Feedback.id).label("rows"),
        )
        .filter(Feedback.scope == "app")
        .group_by(Feedback.kind, Feedback.app_version)
        .order_by(reporters.desc())
        .limit(limit)
        .all()
    )

    # 自由文本单独列:它是 10 种语言进来的,读起来贵,只看还没处理的。
    recent_text = (
        base.filter(Feedback.text.isnot(None), Feedback.status == "new")
        .order_by(Feedback.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "days": days,
        "total": base.count(),
        "pending": base.filter(Feedback.status == "new").count(),
        "objects": [
            {
                "qid": r.qid,
                "title": titles.get(r.qid) or "",
                "language": r.language,
                "kind": r.kind,
                "people": r.people,
                "rows": r.rows,
            }
            for r in by_object
        ],
        "app": [
            {
                "kind": r.kind,
                "app_version": r.app_version,
                "people": r.people,
                "rows": r.rows,
            }
            for r in by_app
        ],
        "texts": [
            {
                "at": f.created_at.isoformat() if f.created_at else None,
                "scope": f.scope,
                "kind": f.kind,
                "qid": f.qid,
                "language": f.language,
                "text": f.text,
            }
            for f in recent_text
        ],
    }


def render(r: dict) -> None:
    print(f"GoMuseum 用户反馈(最近 {r['days']} 天)")
    print(f"├─ 共 {r['total']} 条,待处理 {r['pending']} 条")

    print("├─ 藏品内容(按报告人数排序;people≥2 才值得优先看)")
    if not r["objects"]:
        print("│   (无)")
    for o in r["objects"]:
        dup = f" [{o['rows']}行]" if o["rows"] != o["people"] else ""
        title = f" {o['title'][:28]}" if o["title"] else ""
        print(
            f"│   {o['people']:3d}人{dup} {o['kind']:<16} "
            f"{o['qid']}/{o['language']}{title}"
        )

    print("├─ App 整体")
    if not r["app"]:
        print("│   (无)")
    for a in r["app"]:
        dup = f" [{a['rows']}行]" if a["rows"] != a["people"] else ""
        print(f"│   {a['people']:3d}人{dup} {a['kind']:<16} {a['app_version'] or '-'}")

    print(f"└─ 待处理的自由文本({len(r['texts'])} 条)")
    for t in r["texts"]:
        loc = f"{t['qid']}/{t['language']}" if t["qid"] else t["scope"]
        print(f"    [{t['kind']}] {loc}: {(t['text'] or '')[:80]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    db = SessionLocal()
    try:
        r = build(db, ns.days)
    finally:
        db.close()
    print(json.dumps(r, ensure_ascii=False, indent=2)) if ns.json else render(r)


if __name__ == "__main__":
    main()
