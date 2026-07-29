"""统一权益判断(收费模式定案 2026-07-27)。

**前端不得自行组合 `is_premium` / `day_pass_active` / `expires_at` / `recognition_quota`
做判断** —— 多端各写一套必然不一致(过期没关、退款没撤、恢复购买状态错位)。
一律问这里,前端只看 `can`。

服务端时间为准(客户端时钟不可信)。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models.purchase import Entitlement

# 免费识别次数的真相源是 settings.FREE_RECOGNITION_QUOTA(见 config.py),
# 这里只在 user_benefits 行还不存在时兜底 —— 已存在的行以**该行的剩余数**为准,
# 改配置不会回收老用户额度。

# ─────────────────────────────────────────────────────────────────────────
# 商品目录:**新增 SKU 只改这里一行**(再到商店后台建同名商品即可)。
#
# ⚠️ 价格不在这里 —— 价格永远来自商店(Play/App Store 的 ProductDetails),
# 我们只认商品 ID。这样改价、做地区定价、货币本地化都零代码。
#
# `scope` 决定这张票能解锁哪些馆(见 covers_museum)。此前 scope 列建了、存了,
# 却**从未被任何地方读过** —— 巴黎通票能解锁马德里。又一次"写完了没接上"。
PASSES: dict[str, dict] = {
    "paris_pass_7d": {"days": 7, "scope": "paris"},
    # 以后加:
    # "paris_pass_1d":  {"days": 1,  "scope": "paris"},
    # "madrid_pass_7d": {"days": 7,  "scope": "madrid"},
    # "eu_pass_14d":    {"days": 14, "scope": "*"},      # * = 全部城市
}

# 兼容旧调用点;新代码一律查 PASSES
PASS_DURATION = timedelta(days=PASSES["paris_pass_7d"]["days"])


def is_pass_product(product_id: str) -> bool:
    """是不是通票类商品。**别再用等值判断** —— 第二个 SKU 会掉进老商品分支。"""
    return product_id in PASSES


def pass_duration(product_id: str) -> timedelta:
    return timedelta(days=PASSES.get(product_id, {}).get("days", 7))


def pass_scope(product_id: str) -> str:
    return PASSES.get(product_id, {}).get("scope", "paris")


def covers_museum(scope: str, museum_city: str | None) -> bool:
    """该 scope 是否覆盖此馆。`*` 覆盖全部;否则按城市(大小写不敏感)。"""
    if scope == "*":
        return True
    return bool(museum_city) and museum_city.strip().lower() == scope.lower()


# 免费试听只覆盖**主讲解段**。一件作品还有背景/分析/问答/作者介绍等段落,
# 每段独立 TTS;不限段的话"免费一件"实际是几十次生成(再乘 10 种语言)。
FREE_AUDIO_SECTION = "guide"

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


def _live_entitlement(db, user_id: str, city: str | None = None):
    """取该用户最相关的一条权益:优先 active,其次待激活。已退款/撤销不算。

    [city] 给了就只认**覆盖该城市**的票(scope 校验)。此前 scope 存了却从没读过,
    等于巴黎通票能解锁马德里 —— 多城市那天才会发现,而那时已经在卖了。
    """
    rows = (
        db.query(Entitlement)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.status.in_([ACTIVE, PURCHASED_NOT_ACTIVATED]),
        )
        .order_by(Entitlement.created_at.desc())
        .all()
    )
    if city is not None:
        rows = [r for r in rows if covers_museum(r.scope or "paris", city)]

    # ⚠️ 顺序不能是"status==ACTIVE 就返回":到期只在读取时算,DB 里那行**永远停在
    # ACTIVE**。老票过期后用户续购,新票是 purchased_not_activated,却被那行过期的
    # ACTIVE 永久遮蔽 → resolve_state 恒为 expired、activate() 拒绝 ——
    # **用户付了第二次钱,票永远激活不了**(2026-07-29 外部评审发现,已复现)。
    now = _now()

    def _still_live(r) -> bool:
        exp = _aware(r.expires_at)
        return r.status == ACTIVE and (exp is None or exp > now)

    for r in rows:  # ① 真正生效中的
        if _still_live(r):
            return r
    for r in rows:  # ② 未激活的(优先于已过期的,这是续购的路径)
        if r.status == PURCHASED_NOT_ACTIVATED:
            return r
    return rows[0] if rows else None  # ③ 只剩过期的


def resolve_state(
    db, user_id: str, city: str | None = None
) -> tuple[str, Entitlement | None]:
    """当前权益状态。**到期判断在这里做**,不依赖任何定时任务把 status 刷成 expired
    ——定时任务漏跑就会白送权限。"""
    ent = _live_entitlement(db, user_id, city)
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
    # 时长取自该商品,不是全局常量 —— 否则 1 日票也会发 7 天
    ent.expires_at = now + pass_duration(ent.entitlement_type)
    db.commit()
    return ACTIVE, ent


def summary(db, user_id: str, benefits=None, *, is_guest: bool = False) -> dict:
    """前端唯一入口。`can` 是前端该看的东西,其余字段供展示。

    免费层边界(付费墙建在**现场体验**不在内容):
    - 浏览/搜索/完整文字讲解/接地预设问答 → 永远免费,不在 `can` 里体现
    - 识别 → 免费 5 次,用完需通票
    - 语音 → 首件自动试听(见 free_audio_qid),第二件起需通票

    `can.purchase`:**买票前必须登录**(2026-07-28 定)。通票挂 user_id,而游客
    身份是设备绑定的 —— 游客买了票,换手机/清数据就永久拿不回(收据已消耗,
    恢复购买会命中幂等、不给新用户发权益)。强制登录让权益天然跟着账号走,
    不必再做收据转移。
    """
    state, ent = resolve_state(db, user_id)
    active = state == ACTIVE
    # ⚠️ recognition_quota 是**剩余数**(consume_recognition 每次递减),不是上限。
    # 曾误写成 quota + bonus - used —— 那会重复扣一次 used,少报剩余次数、
    # 让付费墙提前弹(用户初始10次用3次 → 实际剩7,却报成4)。
    quota = getattr(benefits, "recognition_quota", settings.FREE_RECOGNITION_QUOTA)
    bonus = getattr(benefits, "referral_bonus_quota", 0) or 0
    left = max(0, (quota or 0) + bonus)
    free_audio_qid = getattr(benefits, "free_audio_qid", None)
    return {
        "state": state,
        "expires_at": ent.expires_at.isoformat() if ent and ent.expires_at else None,
        "free_recognitions_left": None if active else left,
        # 进度环的分母。前端曾把它写死成 10,后端一调额度就显示 "5/10"
        # (新用户像是已用掉一半)。server-driven:分母也由后端给。
        "free_recognitions_total": (
            None if active else settings.FREE_RECOGNITION_QUOTA + bonus
        ),
        "free_audio_qid": free_audio_qid,
        "can": {
            "purchase": not is_guest,
            "recognize": active or left > 0,
            # 语音:通票内全放行;免费用户只放行已认领的那一件那种语言的主讲解段
            # (`ai_ask` 已移除:自由问答停用中 /chat/ask 返 503,
            #  契约不该承诺一个不存在的能力)
            "audio_any": active,
        },
    }


def can_play_audio(
    db,
    user_id: str,
    qid: str,
    benefits=None,
    *,
    language: str = "zh",
    section: str = FREE_AUDIO_SECTION,
    city: str | None = None,
) -> bool:
    """某件的语音能不能放。

    免费用户只有**已认领的那一件、那种语言、主讲解段**可放(可无限重播)。
    收敛到三元组是因为:一件作品多段 × 10 语言 = 几十次 TTS,
    只按 qid 判等于免费送几十次生成。
    """
    state, _ = resolve_state(db, user_id, city)
    if state == ACTIVE:
        return True
    if section != FREE_AUDIO_SECTION:
        return False
    claimed = getattr(benefits, "free_audio_qid", None)
    claimed_lang = getattr(benefits, "free_audio_lang", None)
    return bool(claimed) and claimed == qid and claimed_lang == language


def claim_free_audio(db, benefits, qid: str, language: str = "zh") -> bool:
    """认领首件免费语音。已认领过则不改(不给第二件)。返回是否本次认领。

    ⚠️ 认领时机=**首次识别成功后自动播放**,不是"给一张待花的券"——
    券式设计的隐患:很多用户到最后都没用过、压根不知道有语音,付费墙就白建了。
    """
    if getattr(benefits, "free_audio_qid", None):
        return False
    benefits.free_audio_qid = qid
    benefits.free_audio_lang = language
    benefits.free_audio_claimed_at = _now()
    db.commit()
    return True


class PurchaseOwnershipConflict(Exception):
    """同一张收据被另一个账号用过。绝不静默成功——付钱的人会以为买到了。"""


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
    if existing:
        # 恢复购买/重复上报:返回已有,不重复发放。
        # ⚠️ 但若这张收据**属于别的账号**,绝不能静默返回成功:
        # B 抢先用 A 的 purchase token 上报 → 权益归 B;A 再上报时命中幂等、
        # 接口却回 verified=true —— A 付了钱、权益在 B 手上,还以为买成功了。
        # 归属不同必须显式失败,让调用方返错误码而不是假成功。
        if existing.user_id != user_id:
            raise PurchaseOwnershipConflict(
                f"purchase {store_transaction_id} belongs to another account"
            )
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
        scope=pass_scope(product_id),
        source_purchase_id=p.id,
        status=PURCHASED_NOT_ACTIVATED,
        granted_reason="purchase",
    )
    db.add(ent)
    db.commit()
    return p, ent


# 老权益(user_benefits.is_premium / day_pass_active)的兼容类型。
# scope="*" —— 老权益没有城市概念,覆盖全部(covers_museum 认 "*")。
LEGACY_PREMIUM = "legacy_premium"
LEGACY_DAY_PASS = "legacy_day_pass"
LEGACY_SCOPE = "*"


def grant_legacy_pass(db, *, user_id: str, kind: str, expires_at, commit=True):
    """给老权益补一张等价的 entitlement。**"新付费规则不得影响老用户权益"的兜底。**

    为什么需要:音频闸门只认 entitlements(见 resolve_state),而老商品
    (premium_annual/day_pass)的购买路径只写 `user_benefits.is_premium` ——
    **老用户付了钱却听不了音频**。既然真相源统一到 entitlements,老权益就必须
    被搬过来,而不是让老用户失效。

    ⭐ status 直接给 `ACTIVE`,不是 purchased_not_activated:老用户此前就在用,
    再要求他点一次"现在开始计时"是凭空多出来的一道坎(而且会让人以为票没了)。

    幂等:同一 user 已有未过期的同类 legacy 权益 → 返回已有,不重复发。
    """
    from app.models.purchase import Entitlement

    exp = _aware(expires_at)
    if exp is not None and exp <= _now():
        return None  # 已过期的老权益不搬(搬过来也是 expired)

    existing = (
        db.query(Entitlement)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.entitlement_type == kind,
            Entitlement.status.in_([ACTIVE, PURCHASED_NOT_ACTIVATED]),
        )
        .first()
    )
    if existing:
        return existing

    ent = Entitlement(
        user_id=user_id,
        entitlement_type=kind,
        scope=LEGACY_SCOPE,
        status=ACTIVE,
        activated_at=_now(),
        expires_at=exp,
        granted_reason="legacy_migration",
    )
    db.add(ent)
    if commit:
        db.commit()
    return ent


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


def audio_access(
    db,
    user_id: str,
    qid: str,
    *,
    language: str = "zh",
    section: str = FREE_AUDIO_SECTION,
    city: str | None = None,
) -> str:
    """语音闸门:**付费墙真正生效的地方**(前端 UI 只是它的表达)。

    返回 "allowed" / "claimable" / "denied",**本身不产生副作用**:
      allowed   通票生效,或这就是已认领的首件(可无限重播)
      claimable 还没认领过任何一件 → 可以放行,但**认领要等音频真的送达**
      denied    其余 → 端点返 402

    ⚠️ 必须在触发 TTS **之前**调用 —— 否则钱已经花掉了,拦也白拦。

    ⚠️ 认领为什么不在这里做(2026-07-28 staging 实测踩到):
    闸门跑在生成之前,而生成可能 404(该语言没正文)/409(生成中)/503。
    在这里认领的话,用户点一件没音频的作品——什么都没听到,免费试听却没了。
    所以认领挪到端点的成功路径上,见 _claim_after_success。
    """
    from app.models.user_benefits import UserBenefits

    benefits = db.query(UserBenefits).filter_by(user_id=user_id).one_or_none()
    if can_play_audio(
        db, user_id, qid, benefits, language=language, section=section, city=city
    ):
        return "allowed"
    if benefits is None:
        return "denied"
    # 只有主讲解段可认领:深度段/问答/作者介绍属付费内容
    if section != FREE_AUDIO_SECTION:
        return "denied"
    return "claimable" if not getattr(benefits, "free_audio_qid", None) else "denied"


def claim_audio_now(db, user_id: str, qid: str, language: str = "zh") -> bool:
    """音频**确实送达后**才认领首件。与 audio_access 的 claimable 配对使用。"""
    from app.models.user_benefits import UserBenefits

    benefits = db.query(UserBenefits).filter_by(user_id=user_id).one_or_none()
    if benefits is None:
        return False
    return claim_free_audio(db, benefits, qid, language)
