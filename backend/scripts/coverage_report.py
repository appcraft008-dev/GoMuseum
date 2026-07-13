"""覆盖率报告 CLI：汇总某馆档案/在线图录/物化/多视角/展陈/识别 KPI 现状，写回
museum.stats["coverage"]（含冗余顶层 catalog_count/archive_count，供 museum_repo pack 读）。

报告 = 展陈状态重算的触发点（spec 定"不做实时"）：build_report 先调
display_state.recompute_display 刷新该馆全部对象的 attributes["display"]，再统计。

用法：
  python scripts/coverage_report.py <slug>
  python scripts/coverage_report.py <slug> --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import and_, distinct, func, or_  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.museum import Museum  # noqa: E402
from app.models.museum_object import MuseumObject, ObjectImage  # noqa: E402
from app.models.object_embedding import ObjectEmbedding  # noqa: E402
from app.models.recognition_event import RecognitionEvent  # noqa: E402
from app.services.coverage.display_state import recompute_display  # noqa: E402
from app.services.museum_repo import _has_image_clause  # noqa: E402


def _get_museum_or_exit(db, museum_slug: str) -> Museum:
    museum = db.query(Museum).filter_by(slug=museum_slug).one_or_none()
    if museum is None:
        raise SystemExit(f"❌ 未知博物馆 slug: {museum_slug}")
    return museum


def build_report(db, museum_slug: str, *, traffic_days: int = 30) -> dict:
    museum = _get_museum_or_exit(db, museum_slug)

    recompute_display(db, museum_slug, traffic_days=traffic_days)  # 报告=状态重算触发点

    archive_count = (
        db.query(func.count(MuseumObject.id)).filter_by(museum_id=museum.id).scalar()
    )
    catalog_count = (
        db.query(func.count(MuseumObject.id))
        .filter_by(museum_id=museum.id)
        .filter(_has_image_clause())
        .scalar()
    )

    embeddings = (
        db.query(func.count(ObjectEmbedding.id))
        .join(MuseumObject, ObjectEmbedding.object_id == MuseumObject.id)
        .filter(MuseumObject.museum_id == museum.id)
        .scalar()
    )
    images_with_key = (
        db.query(func.count(ObjectImage.id))
        .join(MuseumObject, ObjectImage.object_id == MuseumObject.id)
        .filter(MuseumObject.museum_id == museum.id, ObjectImage.image_key.isnot(None))
        .scalar()
    )

    def _image_count(role: str, distinct_objects: bool = False):
        col = func.count(
            distinct(ObjectImage.object_id) if distinct_objects else ObjectImage.id
        )
        return (
            db.query(col)
            .join(MuseumObject, ObjectImage.object_id == MuseumObject.id)
            .filter(MuseumObject.museum_id == museum.id, ObjectImage.role == role)
            .scalar()
        )

    views = {
        "objects": _image_count("view", distinct_objects=True),
        "images": _image_count("view"),
        "quarantined": _image_count("view_quarantine"),
    }

    display: Counter = Counter()
    for obj in db.query(MuseumObject).filter_by(museum_id=museum.id).all():
        status = ((obj.attributes or {}).get("display") or {}).get("status", "UNKNOWN")
        display[status] += 1

    since = datetime.utcnow() - timedelta(days=traffic_days)
    # KPI 归因与 display 证据同口径:老前端带 museum_slug;新前端走全局端点
    # (museum_slug=NULL)按 top_qid 归命中对象所属馆(qid 全局唯一)。
    # 诚实局限:全局端点的未识别事件(top_qid 也 NULL)无法归馆,不计入任何馆 KPI
    # ——分子分母同时缺席,不引入偏差。
    museum_qids = (
        db.query(MuseumObject.qid)
        .filter(MuseumObject.museum_id == museum.id, MuseumObject.qid.isnot(None))
        .scalar_subquery()
    )
    events_q = db.query(RecognitionEvent).filter(
        or_(
            RecognitionEvent.museum_slug == museum_slug,
            and_(
                RecognitionEvent.museum_slug.is_(None),
                RecognitionEvent.top_qid.in_(museum_qids),
            ),
        ),
        RecognitionEvent.created_at >= since,
    )
    attempts = events_q.count()
    hits = (
        events_q.filter(RecognitionEvent.outcome == "match").count()
        + events_q.filter(
            RecognitionEvent.outcome == "candidates",
            RecognitionEvent.confirmed_qid.isnot(None),
        ).count()
    )
    rate = hits / attempts if attempts else None

    return {
        "archive_count": archive_count,
        "catalog_count": catalog_count,
        "textonly_count": archive_count - catalog_count,
        "embeddings": embeddings,
        "images_with_key": images_with_key,
        "views": views,
        "display": dict(display),
        "kpi": {"attempts": attempts, "hits": hits, "rate": rate},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_stats(db, museum_slug: str, report: dict) -> None:
    museum = _get_museum_or_exit(db, museum_slug)
    # MutableDict 对嵌套 mutation 不追踪脏标记，整键重赋值才能让 SQLAlchemy 检测到变化
    museum.stats = {
        **(museum.stats or {}),
        "coverage": report,
        "catalog_count": report["catalog_count"],
        "archive_count": report["archive_count"],
    }
    db.add(museum)
    db.commit()


def _print_human(museum_slug: str, report: dict) -> None:
    print(f"覆盖率报告: {museum_slug}  ({report['generated_at']})")
    print(f"├─ 档案 archive: {report['archive_count']}")
    print(f"│   ├─ 在线图录 catalog(有图): {report['catalog_count']}")
    print(f"│   └─ 待完善 textonly(无图): {report['textonly_count']}")
    print(f"├─ 物化 images_with_key: {report['images_with_key']}")
    print(f"├─ 向量 embeddings: {report['embeddings']}")
    v = report["views"]
    print(
        f"├─ 多视角 views: objects={v['objects']} images={v['images']} quarantined={v['quarantined']}"
    )
    print("├─ 展陈 display")
    for status, n in report["display"].items():
        print(f"│   ├─ {status}: {n}")
    kpi = report["kpi"]
    rate_s = f"{kpi['rate']:.0%}" if kpi["rate"] is not None else "待累计"
    print("└─ 识别 KPI")
    print(f"    ├─ attempts: {kpi['attempts']}")
    print(f"    ├─ hits: {kpi['hits']}")
    print(f"    └─ rate: {rate_s}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="覆盖率报告(状态重算触发点)")
    p.add_argument("slug")
    p.add_argument("--traffic-days", type=int, default=30)
    p.add_argument("--json", action="store_true")
    return p


def main(argv=None) -> None:
    ns = build_parser().parse_args(argv)
    db = SessionLocal()
    try:
        report = build_report(db, ns.slug, traffic_days=ns.traffic_days)
        write_stats(db, ns.slug, report)
    finally:
        db.close()
    if ns.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(ns.slug, report)


if __name__ == "__main__":
    main()
