"""统一权益判断(收费模式定案 2026-07-27)。

**前端不得自行组合 `expires_at` / `recognition_quota` 等字段做判断** ——
多端各写一套必然不一致(过期没关、退款没撤、恢复购买状态错位)。
一律问这里,前端只看 `can`。

(历史:`is_premium` / `day_pass_active` 曾是另一套并行的权益标志,已随老商品
下线一并移除 —— 两套真相源是这类不一致的根源,留着迟早有人去读它。)

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

# 未激活票的**保质期**:买了一直不激活,30 天后作废。
#
# 为什么要有:`purchased_not_activated` 此前**永不过期**,等于每笔收入背一份
# 无限期负债 —— 用户三年后想起来激活,那时的内容/TTS 成本/汇率全变了。
#
# ⚠️ 这是**没收用户已付的款**,两条硬约束不能省:
#   1. **购买前必须披露**。付费墙票面那句「一个月内不激活自动失效」就是披露点,
#      它和这段代码是一对,少了任何一半都不成立(单有文案=骗人,单有代码=偷偷没收)。
#   2. **`created_at` 缺失时不失效**(见 activation_deadline)。宁可漏没收,
#      不可错没收 —— 前者少赚一点,后者是拿了钱不给货。
#
# ponytail: 单一常量,不进 PASSES。真出了保质期不同的 SKU 再挪进商品目录。
ACTIVATION_WINDOW = timedelta(days=30)


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


def activation_deadline(ent) -> datetime | None:
    """未激活票的最后激活时刻。

    返回 `None` = **这张票不失效**:`created_at` 拿不到时(理论上不该发生,
    但它是 server_default 填的,flush 前读就是 None)按"不没收"处理。
    """
    created = _aware(getattr(ent, "created_at", None))
    return None if created is None else created + ACTIVATION_WINDOW


def _unactivated_expired(ent) -> bool:
    """未激活票是否已过保质期。"""
    deadline = activation_deadline(ent)
    return deadline is not None and deadline <= _now()


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
    for r in rows:  # ② 未激活**且还在保质期内**的(优先于已过期的,这是续购的路径)
        if r.status == PURCHASED_NOT_ACTIVATED and not _unactivated_expired(r):
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
        # 买了一直不激活也会作废(见 ACTIVATION_WINDOW)。与 ACTIVE 的到期一样
        # **在读取时算**,不靠定时任务把 status 刷成 expired —— 漏跑就白送权限。
        if _unactivated_expired(ent):
            return EXPIRED, ent
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
    # 未激活票的最后激活时刻,给前端显示「X 月 X 日前激活」。
    # **加法字段**:老 App 不认识就忽略,契约前向兼容。
    activate_by = None
    if state == PURCHASED_NOT_ACTIVATED and ent is not None:
        deadline = activation_deadline(ent)
        activate_by = deadline.isoformat() if deadline else None
    return {
        "state": state,
        "expires_at": ent.expires_at.isoformat() if ent and ent.expires_at else None,
        "activate_by": activate_by,
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


def history(db, user_id: str, limit: int = 20) -> list[dict]:
    """该用户的票据历史,新到旧。权益页的「购买记录」与「上一张票」用它。

    **不塞进 summary()**:summary 是热路径(每次权益判断都调),而历史只有
    权益页要看 —— 混进去等于每次判权益都多查一张表。

    ⚠️ **金额不在这里**。`purchases.amount` 从来没被写过
    (`grant_from_purchase` 的调用方没传),库里恒为 NULL。想补金额得改购买
    上报链路,而那条链路只能靠真机真购买验收。**绝不能拿商店当前售价顶替**
    —— 那是"现在卖多少",不是"当时付了多少",涨一次价收据就开始说谎。
    """
    rows = (
        db.query(Entitlement)
        .filter(Entitlement.user_id == user_id)
        .order_by(Entitlement.created_at.desc())
        .limit(limit)
        .all()
    )
    now = _now()

    def _state(r) -> str:
        """展示用状态。与 resolve_state 同源的判定,但**逐行**算 ——
        resolve_state 只回答"当前哪张票说了算",历史要每张票各自的结局。"""
        if r.status not in (ACTIVE, PURCHASED_NOT_ACTIVATED):
            return r.status  # refunded / revoked 原样透出
        if r.status == PURCHASED_NOT_ACTIVATED:
            return EXPIRED if _unactivated_expired(r) else PURCHASED_NOT_ACTIVATED
        exp = _aware(r.expires_at)
        return EXPIRED if exp and exp <= now else ACTIVE

    def _iso(dt):
        dt = _aware(dt)
        return dt.isoformat() if dt else None

    return [
        {
            "product_id": r.entitlement_type,
            "state": _state(r),
            "purchased_at": _iso(r.created_at),
            "activated_at": _iso(r.activated_at),
            "expires_at": _iso(r.expires_at),
        }
        for r in rows
    ]


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
    # 只有主讲解段可认领:深度段/问答/作者介绍属付费内容
    if section != FREE_AUDIO_SECTION:
        return "denied"
    # ⚠️ benefits 行是**懒建**的(首次 /payment/benefits 或首次识别时才建),
    # 所以"没有行"= 一次都还没用过 = 免费试听**还在**,不是"没有权限"。
    # 这里曾直接 denied —— 于是刚注册的用户在 App 把行建出来之前点听讲解,
    # 迎面就是付费墙(2026-09-19 staging 实证:注册后直接 GET /audio 得 402,
    # 先调一次 /payment/benefits 再调同一个端点就是 200)。
    # 判 claimable 不会白送:名额在 claim_audio_now 里才落库,而它会把行建出来。
    if benefits is None:
        return "claimable"
    return "claimable" if not getattr(benefits, "free_audio_qid", None) else "denied"


def claim_audio_now(db, user_id: str, qid: str, language: str = "zh") -> bool:
    """音频**确实送达后**才认领首件。与 audio_access 的 claimable 配对使用。

    行不存在就建一行再认领 —— 认领是**写**路径,建行天经地义;
    判定那侧仍然一个字节都不写(见 audio_access 的副作用约束)。
    没有这一步,上面放行的 claimable 就会认领失败,变成"每一件都免费"。

    ⚠️ 这里拿不到 `device_id`(音频端点的身份一律取自令牌,不收设备参数),
    所以建行时**不做匿名行归并**——那件事归 `/payment/benefits` 管,它带 device_id。
    实际顺序上 App 一启动就会调那个端点,轮不到这里建行;真轮到了(裸调 API),
    代价是该设备的匿名额度没被归并,不会产生同一 user 的第二行(按 user_id 查在先)。
    """
    from app.services.benefits_service import BenefitsService

    benefits = BenefitsService(db).get_or_create_benefits(user_id=user_id)
    return claim_free_audio(db, benefits, qid, language)
