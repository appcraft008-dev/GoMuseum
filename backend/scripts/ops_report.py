"""MVP 运营周报(P0-d,2026-07-27)。

**不建后台**:100 个测试用户的数据,一条命令 + 一屏输出就够,建仪表盘的时间
够多招 50 个用户。沿用项目已有模式(llm_cost_report / coverage-report / verify)。

⚠️ 按馆统计必须**用命中对象的归属馆归因** —— App 走全局识别端点,
`recognition_events.museum_slug` 基本为空(实测 244 条全空)。

用法(容器内):
  python scripts/ops_report.py [--days 7] [--json]
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from sqlalchemy import func  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.app_event import AppEvent  # noqa: E402
from app.models.museum import Museum  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402
from app.models.purchase import Entitlement, Purchase  # noqa: E402
from app.models.recognition_demand import RecognitionDemand  # noqa: E402
from app.models.recognition_event import RecognitionEvent  # noqa: E402
from app.models.user_benefits import UserBenefits  # noqa: E402


def _since(days: int):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _museum_by_qid(db) -> dict:
    """qid → 馆 slug。识别事件的 museum_slug 常为空(全局端点),按命中对象归因。"""
    slug_by_id = dict(db.query(Museum.id, Museum.slug))
    return {
        qid: slug_by_id.get(mid)
        for qid, mid in db.query(MuseumObject.qid, MuseumObject.museum_id)
    }


def build(db, days: int) -> dict:
    since = _since(days)
    ev = db.query(AppEvent).filter(AppEvent.created_at >= since)
    counts = Counter(n for (n,) in ev.with_entities(AppEvent.name))

    users_total = db.query(UserBenefits).count()
    paid = db.query(Entitlement).filter(Entitlement.status == "active").count()
    pending = (
        db.query(Entitlement)
        .filter(Entitlement.status == "purchased_not_activated")
        .count()
    )

    # 识别:按命中对象归因到馆(全局端点导致 museum_slug 为空)
    by_qid = _museum_by_qid(db)
    per_museum: dict = {}
    for slug, outcome, qid in db.query(
        RecognitionEvent.museum_slug, RecognitionEvent.outcome, RecognitionEvent.top_qid
    ).filter(RecognitionEvent.created_at >= since):
        m = slug or by_qid.get(qid) or "(未归因)"
        d = per_museum.setdefault(m, Counter())
        d[outcome] += 1

    # 失败需求 = 用户真拍却认不出 → 补图优先级(比盲目全量补图精准得多)
    demand = [
        (t or "(无墙签)", n)
        for t, n in db.query(RecognitionDemand.label_text, func.count())
        .filter(RecognitionDemand.created_at >= since)
        .group_by(RecognitionDemand.label_text)
        .order_by(func.count().desc())
        .limit(5)
    ]

    # 跨馆复用:MVP 最重要的新指标
    museums_per_user = Counter()
    for uid, slug in (
        db.query(AppEvent.user_id, AppEvent.museum_slug)
        .filter(AppEvent.name == "museum_used", AppEvent.created_at >= since)
        .distinct()
    ):
        if uid:
            museums_per_user[uid] += 1
    dist = Counter(museums_per_user.values())
    multi = sum(v for k, v in dist.items() if k >= 2)
    reuse = 100.0 * multi / len(museums_per_user) if museums_per_user else 0.0

    triggers = Counter(
        (e.props or {}).get("trigger", "?")
        for e in ev.filter(AppEvent.name == "purchase_succeeded")
    )
    entries = Counter(
        (e.props or {}).get("from", "?")
        for e in ev.filter(AppEvent.name == "content_viewed")
    )

    return {
        "days": days,
        "users": {"total": users_total, "pass_active": paid, "pass_pending": pending},
        "funnel": {
            k: counts.get(k, 0)
            for k in (
                "recognition_succeeded",
                "free_quota_exhausted",
                "paywall_viewed_from_audio",
                "paywall_viewed_from_quota",
                "paywall_viewed_from_ai",
                "purchase_started",
                "purchase_succeeded",
                "purchase_failed",
                "pass_activated",
            )
        },
        "purchase_triggers": dict(triggers),
        "content_entries": dict(entries),
        "recognition_by_museum": {m: dict(c) for m, c in per_museum.items()},
        "demand_top": demand,
        "cross_museum": {
            "users": len(museums_per_user),
            "multi": multi,
            "reuse_pct": round(reuse, 1),
            "dist": dict(dist),
        },
        "revenue_eur": float(
            db.query(func.coalesce(func.sum(Purchase.amount), 0))
            .filter(Purchase.status == "purchased", Purchase.created_at >= since)
            .scalar()
            or 0
        ),
    }


def render(r: dict) -> None:
    print(f"GoMuseum 运营报告(最近 {r['days']} 天)")
    u = r["users"]
    print(
        f"├─ 用户  总 {u['total']} · 通票生效 {u['pass_active']} · 已购未激活 {u['pass_pending']}"
    )
    f = r["funnel"]
    print("├─ 付费漏斗")
    print(
        f"│   识别成功 {f['recognition_succeeded']} → 额度耗尽 {f['free_quota_exhausted']}"
        f" → 付费页 {f['paywall_viewed_from_audio']+f['paywall_viewed_from_quota']+f['paywall_viewed_from_ai']}"
        f"(语音{f['paywall_viewed_from_audio']}/额度{f['paywall_viewed_from_quota']}/问答{f['paywall_viewed_from_ai']})"
    )
    print(
        f"│   发起购买 {f['purchase_started']} → 成功 {f['purchase_succeeded']}"
        f"(失败 {f['purchase_failed']}) → 激活 {f['pass_activated']}"
    )
    if r["purchase_triggers"]:
        print(f"│   为什么付费: {r['purchase_triggers']}")
    if r["content_entries"]:
        print(f"├─ 内容入口(判断搜索是否绕过付费): {r['content_entries']}")
    print("├─ 识别(按命中对象归因到馆)")
    for m, c in sorted(r["recognition_by_museum"].items()):
        tot = sum(c.values())
        ok = c.get("match", 0) + c.get("candidates", 0)
        rate = f"{100.0*ok/tot:.1f}%" if tot else "-"
        print(
            f"│   {m:12s} 尝试 {tot:4d}  命中 {ok:4d} ({rate})  未识别 {c.get('unrecognized',0)}"
        )
    if r["demand_top"]:
        print("├─ 拍了却认不出 TOP(补图优先级)")
        for t, n in r["demand_top"]:
            print(f"│   {n:3d}× {str(t)[:46]}")
    cm = r["cross_museum"]
    print(
        f"├─ 跨馆复用  用过≥2馆 {cm['multi']}/{cm['users']} = {cm['reuse_pct']}%  分布 {cm['dist']}"
    )
    print(f"└─ 收入 €{r['revenue_eur']:.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
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
