"""统一权益判断(收费模式定案 2026-07-27)。

**前端不得自行组合 `is_premium` / `day_pass_active` / `expires_at` / `recognition_quota`
做判断** —— 多端各写一套必然不一致(过期没关、退款没撤、恢复购买状态错位)。
一律问这里,前端只看 `can`。

服务端时间为准(客户端时钟不可信)。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.purchase import Entitlement

# 跨馆免费识别次数。⚠️ 仅当 user_benefits 行不存在时的兜底,**真相源是 DB 里那一列**
# (模型 default=10)。2026-07-27 曾误以为线上是 3 次、讨论要"给更多改成 5"——
# 实测 prod 真实用户都是 10,改 5 反而是砍半。保持与模型 default 一致。
FREE_RECOGNITIONS = 10
PASS_DURATION = timedelta(days=7)

# 权益状态(对外统一口径)
NOT_PURCHASED = "not_purchased"
PURCHASED_NOT_ACTIVATED = "purchased_not_activated"
ACTIVE = "active"
EXPIRED = "expired"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """DB 回来的时间统一成 aware(SQLite 不存时区;Postgres 存)。
    naive 一律按 UTC 解读——服务端时间为准,不猜本地时区。"""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def _live_entitlement(db, user_id: str):
    """取该用户最相关的一条权益:优先 active,其次待激活。已退款/撤销不算。"""
    rows = (
        db.query(Entitlement)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.status.in_([ACTIVE, PURCHASED_NOT_ACTIVATED]),
        )
        .order_by(Entitlement.created_at.desc())
        .all()
    )
    for r in rows:  # active 优先(可能同时存在待激活的第二张)
        if r.status == ACTIVE:
            return r
    return rows[0] if rows else None


def resolve_state(db, user_id: str) -> tuple[str, Entitlement | None]:
    """当前权益状态。**到期判断在这里做**,不依赖任何定时任务把 status 刷成 expired
    ——定时任务漏跑就会白送权限。"""
    ent = _live_entitlement(db, user_id)
    if ent is None:
        return NOT_PURCHASED, None
    if ent.status == PURCHASED_NOT_ACTIVATED:
        return PURCHASED_NOT_ACTIVATED, ent
    if _aware(ent.expires_at) and _aware(ent.expires_at) <= _now():
        return EXPIRED, ent
    return ACTIVE, ent


def activate(db, user_id: str) -> tuple[str, Entitlement | None]:
    """首次使用高级功能且用户确认后调用:开始连续 7×24h。幂等(已激活直接返回)。"""
    state, ent = resolve_state(db, user_id)
    if state != PURCHASED_NOT_ACTIVATED or ent is None:
        return state, ent
    now = _now()
    ent.status = ACTIVE
    ent.activated_at = now
    ent.expires_at = now + PASS_DURATION
    db.commit()
    return ACTIVE, ent


def summary(db, user_id: str, benefits=None) -> dict:
    """前端唯一入口。`can` 是前端该看的东西,其余字段供展示。

    免费层边界(付费墙建在**现场体验**不在内容):
    - 浏览/搜索/完整文字讲解/接地预设问答 → 永远免费,不在 `can` 里体现
    - 识别 → 免费 5 次,用完需通票
    - 语音 → 首件自动试听(见 free_audio_qid),第二件起需通票
    """
    state, ent = resolve_state(db, user_id)
    active = state == ACTIVE
    used = getattr(benefits, "total_recognitions_used", 0) or 0
    quota = getattr(benefits, "recognition_quota", FREE_RECOGNITIONS)
    bonus = getattr(benefits, "referral_bonus_quota", 0) or 0
    left = max(0, (quota or 0) + bonus - used)
    free_audio_qid = getattr(benefits, "free_audio_qid", None)
    return {
        "state": state,
        "expires_at": ent.expires_at.isoformat() if ent and ent.expires_at else None,
        "free_recognitions_left": None if active else left,
        "free_audio_qid": free_audio_qid,
        "can": {
            "recognize": active or left > 0,
            # 语音:通票内全放行;免费用户只放行已认领的那一件
            "audio_any": active,
            "ai_ask": active,
        },
    }


def can_play_audio(db, user_id: str, qid: str, benefits=None) -> bool:
    """某件的语音能不能放。免费用户只有已认领的首件可放(可无限重播)。"""
    state, _ = resolve_state(db, user_id)
    if state == ACTIVE:
        return True
    claimed = getattr(benefits, "free_audio_qid", None)
    return bool(claimed) and claimed == qid


def claim_free_audio(db, benefits, qid: str) -> bool:
    """认领首件免费语音。已认领过则不改(不给第二件)。返回是否本次认领。

    ⚠️ 认领时机=**首次识别成功后自动播放**,不是"给一张待花的券"——
    券式设计的隐患:很多用户到最后都没用过、压根不知道有语音,付费墙就白建了。
    """
    if getattr(benefits, "free_audio_qid", None):
        return False
    benefits.free_audio_qid = qid
    benefits.free_audio_claimed_at = _now()
    db.commit()
    return True


PARIS_PASS_7D = "paris_pass_7d"


def grant_from_purchase(
    db,
    *,
    user_id: str,
    platform: str,
    product_id: str,
    store_transaction_id: str,
    amount=None,
    currency=None,
    receipt_payload=None,
) -> tuple:
    """收据校验通过后:落订单 + 发权益。返回 (purchase, entitlement)。

    **幂等靠 store_transaction_id 唯一** —— 恢复购买会重复上报同一 token,
    重复调用只返回已有记录,绝不发第二张票(重复发放=白送钱)。

    ⭐ 发出的权益是 `purchased_not_activated`,**不开始计时**:旅游产品用户
    常提前几天买,立即计时会白烧有效期;首次用高级功能且用户确认才 activate()。
    """
    from app.models.purchase import Entitlement, Purchase

    existing = (
        db.query(Purchase)
        .filter_by(store_transaction_id=store_transaction_id)
        .one_or_none()
    )
    if existing:  # 恢复购买/重复上报:返回已有,不重复发放
        ent = (
            db.query(Entitlement)
            .filter_by(source_purchase_id=existing.id)
            .one_or_none()
        )
        return existing, ent

    p = Purchase(
        user_id=user_id,
        platform=platform,
        product_id=product_id,
        store_transaction_id=store_transaction_id,
        amount=amount,
        currency=currency,
        status="purchased",
        purchased_at=_now(),
        receipt_payload=receipt_payload,
    )
    db.add(p)
    db.flush()  # 拿 p.id 关联权益
    ent = Entitlement(
        user_id=user_id,
        entitlement_type=product_id,
        scope="paris",
        source_purchase_id=p.id,
        status=PURCHASED_NOT_ACTIVATED,
        granted_reason="purchase",
    )
    db.add(ent)
    db.commit()
    return p, ent


def revoke_for_purchase(
    db, store_transaction_id: str, reason: str = "refunded"
) -> bool:
    """退款/撤销:订单与权益一并标记。供商店回调(RTDN)或人工使用。
    **权益必须跟着撤** —— 只标订单不撤权益 = 退了钱还能用。"""
    from app.models.purchase import Entitlement, Purchase

    p = (
        db.query(Purchase)
        .filter_by(store_transaction_id=store_transaction_id)
        .one_or_none()
    )
    if not p:
        return False
    p.status = reason
    p.refunded_at = _now()
    for ent in db.query(Entitlement).filter_by(source_purchase_id=p.id):
        ent.status = reason
    db.commit()
    return True
