"""退款对账 —— 补上 RTDN 漏掉的退款,把权益撤回来。

## 为什么需要它(RTDN 已经有了,为什么还要对账)

`/payment/rtdn` 是**推送**:Google 主动通知我们某笔退了。推送这种东西天然会丢 ——
Pub/Sub 重试若干天后放弃、订阅配错、我们这侧那几分钟正好在部署重启、
IAM 权限被改掉(2026-09-02 就发生过:缺 Pub/Sub 发布者权限,通知一条都收不到)。
丢一条的后果不是"少一条日志",而是**用户退了钱、通票照用满 7 天**,
而且**没有任何地方会报错** —— 账面一切正常,钱就那么漏了。

推送只能做**及时**,不能做**兜底**。兜底必须是**主动拉取**,也就是这个脚本。

## 为什么不用 voidedpurchases.list

那是官方的"退款清单"接口,看起来正是为此而生。实测(2026-09-02)**三组参数
全部返回空**,而 Console 侧也没有 revoke 入口 —— 测试订单的退款根本不进这个 feed。
也就是说:它返回空,和"确实没有退款"**不可区分**。一个永远返回空的兜底
等于没有兜底,而且它绿着,比没有更危险。

这里改问**另一个问题**:我们库里存着每一笔的 purchase token
(`purchases.receipt_payload`),直接问 Play「**这一笔现在什么状态**」。
`purchaseState=1` = Canceled(退款/撤销)。这条路的好处是:
  - 不依赖任何通知/清单 feed,只依赖我们自己已经存下的东西
  - **今天就能验证**:拿 prod 上真实那几笔跑一遍,该返回 0(Purchased)
  - 天然有界:只查**当前还生效**的权益,过期的票退不退款都无所谓

## 护栏(比功能本身重要 —— 撤权益是拿走用户已经付过钱的东西)

- **默认 dry-run**,必须显式 `--apply`
- **凭证不可用直接非零退出**,绝不把"问不到"报成"没有退款"
- **撤销比例上限**(默认 20%):Play 换语义、包名配错、服务账号换了项目,
  都会让一整批查询"看起来像全退款了"。宁可不撤,等人来看
- **逐笔独立**:某一笔查询出错只影响那一笔(计入 unknown),不影响其余

用法:
  python scripts/reconcile_refunds.py                 # 只报告
  python scripts/reconcile_refunds.py --apply
  python scripts/reconcile_refunds.py --apply --max-revoke-ratio 0.5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.purchase import Entitlement, Purchase  # noqa: E402
from app.services import entitlement_service as es  # noqa: E402
from app.services.iap_verification_service import (  # noqa: E402
    get_iap_verification_service,
)

# Play `purchases.products.get` 的 purchaseState:0=Purchased 1=Canceled 2=Pending
PLAY_STATE_CANCELED = 1

# 只有这两个状态的权益还值得对账 —— 已过期/已撤销的票,退不退款都改变不了什么
LIVE_STATUSES = (es.ACTIVE, es.PURCHASED_NOT_ACTIVATED)


class NoCredentials(Exception):
    """没有 Play 凭证 = 什么都问不到。**绝不能静默当成"没有退款"**。"""


def live_google_purchases(db) -> list[Purchase]:
    """当前还生效的权益背后那些 Google 订单(去重,按订单)。

    从**权益**这侧出发而不是从订单出发:我们要保护的是"还能用的票",
    一笔早已过期的订单即使退了款也无事可做。这让扫描量恒等于活跃付费用户数。
    """
    purchase_ids = {
        pid
        for (pid,) in db.query(Entitlement.source_purchase_id)
        .filter(
            Entitlement.status.in_(LIVE_STATUSES),
            Entitlement.source_purchase_id.isnot(None),
        )
        .distinct()
        if pid is not None
    }
    if not purchase_ids:
        return []
    return (
        db.query(Purchase)
        .filter(
            Purchase.id.in_(purchase_ids),
            Purchase.platform == "android",
            Purchase.status == "purchased",
            # 删号会把 receipt_payload 清空(个人数据),那种行查不了也不必查
            Purchase.receipt_payload.isnot(None),
        )
        .all()
    )


# 比例闸的**绝对下限**:少于这么多笔时不看比例,照撤。
#
# ⚠️ 没有这条,闸会在早期把每一笔真实退款都挡住 —— 只有 1 个活跃付费用户时,
# 他退款就是 100%,永远超过任何比例上限。那样这个脚本从上线第一天起就不生效,
# 而且**是绿的**:报告里写着"已中止,等人确认",没有人会去确认。
# 一次误判最多撤掉这么几张票(可人工补发);而挡住真实退款是**必然漏钱**。
MIN_BATCH_FOR_RATIO_GUARD = 3


async def reconcile(
    db,
    iap=None,
    *,
    apply: bool = False,
    max_revoke_ratio: float = 0.2,
) -> dict:
    """对一遍账。返回报告 dict;`apply=False` 时只报不改。

    抛 [NoCredentials] 表示这次对账**没有发生** —— 调用方必须当失败处理,
    而不是当成"查过了,干净"。
    """
    iap = iap or get_iap_verification_service()
    if iap._play_access_token() is None:
        raise NoCredentials("GOOGLE_PLAY_SERVICE_ACCOUNT 未配置或不可用")

    purchases = live_google_purchases(db)
    refunded: list[str] = []
    unknown: list[dict] = []
    ok = 0

    for p in purchases:
        try:
            res = await iap.verify_google_receipt(
                purchase_token=p.receipt_payload, product_id=p.product_id
            )
        except Exception as e:  # 逐笔独立:一笔炸了不连累其余
            unknown.append({"order": p.store_transaction_id, "error": repr(e)})
            continue

        if res.get("error"):
            # 查不到 ≠ 已退款。404 也算这里:token 未知与 token 过期无法区分,
            # 拿它去撤票就是**凭"问不出来"没收用户的东西**。
            unknown.append({"order": p.store_transaction_id, "error": res["error"]})
        elif res.get("status") == PLAY_STATE_CANCELED:
            refunded.append(p.store_transaction_id)
        else:
            ok += 1

    report = {
        "scanned": len(purchases),
        "ok": ok,
        "refunded": refunded,
        "unknown": unknown,
        "applied": False,
        "aborted": None,
    }

    if not refunded or not apply:
        return report

    # ⚠️ 批量撤销的闸:Play 换语义 / 包名配错 / 服务账号换了项目,都会让一整批
    # 查询"看起来像全退款了"。宁可一笔不撤,等人来看 —— 撤错的代价是
    # 付了钱的用户当场失去通票,比晚撤几小时严重得多。
    ratio = len(refunded) / len(purchases)
    allowed = max(MIN_BATCH_FOR_RATIO_GUARD, max_revoke_ratio * len(purchases))
    if len(refunded) > allowed:
        report["aborted"] = (
            f"{len(refunded)}/{len(purchases)} ({ratio:.0%}) 超过闸 "
            f"(上限 {max_revoke_ratio:.0%},下限 {MIN_BATCH_FOR_RATIO_GUARD} 笔),"
            f"一笔未撤。确认无误后加 --max-revoke-ratio 放宽"
        )
        return report

    for order_id in refunded:
        es.revoke_for_purchase(db, order_id, reason="refunded")
    report["applied"] = True
    return report


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="退款对账:撤回 RTDN 漏掉的退款权益")
    ap.add_argument("--apply", action="store_true", help="真的撤销(默认只报告)")
    ap.add_argument(
        "--max-revoke-ratio",
        type=float,
        default=0.2,
        help="单次撤销占活跃订单的比例上限,超过则中止(默认 0.2)",
    )
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    db = SessionLocal()
    try:
        report = asyncio.run(
            reconcile(db, apply=args.apply, max_revoke_ratio=args.max_revoke_ratio)
        )
    except NoCredentials as e:
        # 非零退出:cron 的告警靠它。报成 "0 refunds" 才是最坏的结果 ——
        # 那会让一个从来没真正跑起来的对账任务看起来天天正常。
        print(f"❌ 对账未执行:{e}", file=sys.stderr)
        return 2
    finally:
        db.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            f"扫描 {report['scanned']} 笔活跃订单:正常 {report['ok']}、"
            f"退款 {len(report['refunded'])}、查不到 {len(report['unknown'])}"
        )
        for u in report["unknown"]:
            print(f"  ⚠️ 查不到 {u['order']}: {u['error']}")
        for o in report["refunded"]:
            print(f"  💸 已退款 {o}{'(已撤销)' if report['applied'] else '(未撤销)'}")
        if report["aborted"]:
            print(f"⛔ {report['aborted']}", file=sys.stderr)
        if report["refunded"] and not report["applied"] and not report["aborted"]:
            print("（dry-run:加 --apply 才会真的撤销）")

    if report["aborted"]:
        return 3
    # 查不到的那些也要能告警:它们是"对账有盲区"，不是"对账干净"
    return 1 if report["unknown"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
