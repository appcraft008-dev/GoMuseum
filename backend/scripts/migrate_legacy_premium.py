"""老权益迁移:user_benefits.is_premium / day_pass_active → entitlements。

**为什么要迁**:付费墙把权益真相源统一到 `entitlements`(音频闸门 `can_play_audio`
→ `resolve_state` 只查这张表),而老商品(premium_annual / day_pass)的购买路径只写
`user_benefits`。两者不通 → **老用户付了钱却听不了音频**,违反"新付费规则不得
影响老用户权益"。

存量靠本脚本搬,增量靠 payment.py 老商品分支里的 grant_legacy_pass(源头已堵)。

用法(容器内):
    python scripts/migrate_legacy_premium.py                 # dry-run,只报不写
    python scripts/migrate_legacy_premium.py --apply         # 真写

幂等:已有未过期同类 legacy 权益的用户会被跳过,重复跑不会发第二张。
"""

import argparse
import sys

sys.path.insert(0, "/app")

from app.core.database import SessionLocal  # noqa: E402
from app.models.purchase import Entitlement  # noqa: E402
from app.models.user_benefits import UserBenefits  # noqa: E402
from app.services import entitlement_service as es  # noqa: E402


def collect(db):
    """挑出需要迁移的 (user_id, kind, expires_at)。无 user_id 的行跳过 ——
    entitlements 按 user_id 索引,只绑 device_id 的老行无处可挂。"""
    todo = []
    for b in db.query(UserBenefits).all():
        if not b.user_id:
            continue
        if b.is_premium and b.premium_expires_at:
            todo.append((b.user_id, es.LEGACY_PREMIUM, b.premium_expires_at))
        if b.day_pass_active and b.day_pass_expires_at:
            todo.append((b.user_id, es.LEGACY_DAY_PASS, b.day_pass_expires_at))
    return todo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写;缺省只报不写")
    ns = ap.parse_args()

    db = SessionLocal()
    try:
        todo = collect(db)
        print(f"待迁移候选 {len(todo)} 条(含已过期与已存在的,下面逐条判定):")
        granted = skipped = expired = 0
        for user_id, kind, exp in todo:
            exp_aware = es._aware(exp)
            if exp_aware is not None and exp_aware <= es._now():
                print(f"  [过期跳过] {user_id[:8]}… {kind} exp={exp}")
                expired += 1
                continue
            already = (
                db.query(Entitlement)
                .filter(
                    Entitlement.user_id == user_id,
                    Entitlement.entitlement_type == kind,
                    Entitlement.status.in_([es.ACTIVE, es.PURCHASED_NOT_ACTIVATED]),
                )
                .first()
            )
            if already:
                print(f"  [已存在]   {user_id[:8]}… {kind}")
                skipped += 1
                continue
            print(
                f"  [{'迁移' if ns.apply else '将迁移'}]   {user_id[:8]}… {kind} exp={exp}"
            )
            granted += 1
            if ns.apply:
                es.grant_legacy_pass(
                    db, user_id=user_id, kind=kind, expires_at=exp, commit=False
                )
        if ns.apply:
            db.commit()
            print(
                f"\n✓ 迁移完成: 新发 {granted} / 已存在 {skipped} / 过期跳过 {expired}"
            )
        else:
            print(
                f"\n(dry-run) 将新发 {granted} / 过期跳过 {expired}"
                f" —— 加 --apply 才真写"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
