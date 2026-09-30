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
#
# scope 语法(spec 2026-09-28-multi-city-expansion §3.1):
#   city:paris   按馆的 city_en(大小写不敏感)
#   country:NL   按馆的 country(ISO 3166-1 alpha-2)
#   *            全部
#   paris        旧写法 = city:paris(DB 里已发出的 Entitlement.scope 不迁移)
# **城市票还是国家票是这里的配置,改它不用发版** —— 前端只显示 `label`,不知道是哪种。
#
# `label`:范围名(十语),付费墙「{label} {days} 日通票」与票面刻印用它。
# `on_sale`:False = 目录里有、但不下发给前端(演练期/尚未在商店生效)。
PASSES: dict[str, dict] = {
    "paris_pass_7d": {
        "days": 7,
        "scope": "city:paris",
        "label": {
            "zh": "巴黎",
            "zh-hant": "巴黎",
            "en": "Paris",
            "fr": "Paris",
            "de": "Paris",
            "es": "París",
            "it": "Parigi",
            "ja": "パリ",
            "ko": "파리",
            "pl": "Paryż",
        },
    },
    "nl_pass_7d": {
        "days": 7,
        "scope": "country:NL",
        "label": {
            "zh": "荷兰",
            "zh-hant": "荷蘭",
            "en": "Netherlands",
            "fr": "Pays-Bas",
            "de": "Niederlande",
            "es": "Países Bajos",
            "it": "Paesi Bassi",
            "ja": "オランダ",
            "ko": "네덜란드",
            "pl": "Holandia",
        },
        # 2026-09-29 Play 商品已建。在售≠公众可见:offers/covers 只列覆盖**已放出**馆的票,
        # 国立博物馆隐身期间只有 can_preview 账号看得到、买得到(演练购买链路用)。
        "on_sale": True,
    },
}

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
    """未知商品 → 空范围(不覆盖任何馆)。此前默认 "paris":新国家漏配商品时
    会静默变成一张巴黎票。宁可锁住,不可错放。"""
    return PASSES.get(product_id, {}).get("scope", "")


def covers_museum(scope: str | None, museum) -> bool:
    """该 scope 是否覆盖此馆(`museum` 需有 city_en / country)。"""
    if not scope or museum is None:
        return False
    if scope == "*":
        return True
    kind, _, value = scope.partition(":")
    if not value:  # 旧写法 "paris"
        kind, value = "city", kind
    if kind == "city":
        city = (getattr(museum, "city_en", None) or "").strip().lower()
        return bool(city) and city == value.strip().lower()
    if kind == "country":
        country = (getattr(museum, "country", None) or "").strip().upper()
        return bool(country) and country == value.strip().upper()
    return False


def pass_for_museum(museum) -> str | None:
    """这家馆**在售**的通票商品 ID;没有 → None(该馆不能放出,见 onboard_verify)。
    馆包、402 下发的商品都从这里来 —— 单一真相源。"""
    for pid, p in PASSES.items():
        if p.get("on_sale", True) and covers_museum(p["scope"], museum):
            return pid
    return None


def museum_of_qid(db, qid: str | None):
    """藏品所属的馆(计费按**作品所在的馆**判,不按 URL 里的 slug —— 后者可以随便填)。"""
    if not qid:
        return None
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject

    return (
        db.query(Museum)
        .join(MuseumObject, MuseumObject.museum_id == Museum.id)
        .filter(MuseumObject.qid == qid)
        .first()
    )


def pass_label(product_id: str, language: str) -> str | None:
    label = PASSES.get(product_id, {}).get("label") or {}
    return label.get(language) or label.get("en")


# 票名「<范围> <天数> 日通票」的十语拼法。票名放后端:出单馆票/年票这类新票种时
# 在 PASSES 里写 `title`(十语)覆盖公式即可,前端不用发版。
_TITLE_FMT = {
    "zh": "{label} {days} 日通票",
    "zh-hant": "{label} {days} 日通票",
    "en": "{label} {days}-Day Pass",
    "fr": "Pass {label} {days} jours",
    "de": "{label}-Pass für {days} Tage",
    "es": "Pase de {label} de {days} días",
    "it": "Pass {label} {days} giorni",
    "ja": "{label} {days}日間パス",
    "ko": "{label} {days}일 패스",
    "pl": "Karnet na {days} dni – {label}",
}


def pass_title(product_id: str, language: str) -> str | None:
    """完整票名。认不出的票 → None(前端退回通用文案,不编地名)。"""
    p = PASSES.get(product_id)
    if p is None:
        return None
    own = p.get("title") or {}
    if own.get(language) or own.get("en"):
        return own.get(language) or own.get("en")
    fmt = _TITLE_FMT.get(language) or _TITLE_FMT["en"]
    return fmt.format(label=pass_label(product_id, language), days=p["days"])


def pass_offer(db, museum, language: str = "zh", *, preview: bool = False):
    """下发给前端的通票形状(馆包 / 402 共用)。没有在售商品 → None,
    前端显示「暂未开售」,**绝不回落到巴黎票**。

    `covers` = 该票范围内**已放出**的馆的本地化馆名(预览者连隐身馆一起),
    替代前端写死四馆名的卖点文案 —— 上新馆自动变长,不用发版。"""
    pid = pass_for_museum(museum)
    if pid is None:
        return None
    return _offer(pid, _museums(db, preview), language)


def pass_offers(db, language: str = "zh", *, preview: bool = False) -> list[dict]:
    """全部可买的票(`/me.offers`)—— 给**不知道用户在哪家馆**的购买入口用
    (首页/设置进权益页、识别前置闸撞墙)。每张各一个购买按钮,不猜"第一张"。

    只列覆盖至少一家**已放出**馆的在售票:否则演练期的票会从这里漏给公众。"""
    museums = _museums(db, preview)
    out = []
    for pid, p in PASSES.items():
        if not p.get("on_sale", True):
            continue
        offer = _offer(pid, museums, language)
        if offer["covers"]:
            out.append(offer)
    return out


def _museums(db, preview: bool) -> list:
    from app.models.museum import Museum

    q = db.query(Museum)
    if not preview:
        q = q.filter(Museum.published_at.isnot(None))
    return sorted(q.all(), key=lambda m: m.slug)


def _offer(pid: str, museums: list, language: str) -> dict:
    from app.services.museum_repo import museum_name

    scope = PASSES[pid]["scope"]
    return {
        "product_id": pid,
        "days": PASSES[pid]["days"],
        "label": pass_label(pid, language),
        "title": pass_title(pid, language),
        "covers": [
            museum_name(m, language) for m in museums if covers_museum(scope, m)
        ],
    }


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


def _live_entitlement(db, user_id: str, museum=None):
    """取该用户最相关的一条权益:优先 active,其次待激活。已退款/撤销不算。

    [museum] 给了就只认**覆盖这家馆**的票(scope 校验)。此前 scope 存了却从没读过,
    等于巴黎通票能解锁马德里 —— 多城市那天才会发现,而那时已经在卖了。
    不给 = 任意一张票(设置页/识别前置闸这类"还不知道是哪家馆"的场合)。
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
    if museum is not None:
        # 老行 scope 为空 = 当年只卖巴黎票
        rows = [r for r in rows if covers_museum(r.scope or "paris", museum)]

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


def resolve_state(db, user_id: str, museum=None) -> tuple[str, Entitlement | None]:
    """当前权益状态。**到期判断在这里做**,不依赖任何定时任务把 status 刷成 expired
    ——定时任务漏跑就会白送权限。[museum] 见 _live_entitlement。"""
    ent = _live_entitlement(db, user_id, museum)
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


def activate(db, user_id: str, museum=None) -> tuple[str, Entitlement | None]:
    """首次使用高级功能且用户确认后调用:开始连续 7×24h。幂等(已激活直接返回)。

    [museum] 给了就只激活**覆盖这家馆**的那张 —— 同时持巴黎、荷兰两张未激活票时,
    在荷兰点激活绝不能烧掉巴黎那张(spec 2026-09-28 §2.2)。"""
    state, ent = resolve_state(db, user_id, museum)
    if state != PURCHASED_NOT_ACTIVATED or ent is None:
        return state, ent
    now = _now()
    ent.status = ACTIVE
    ent.activated_at = now
    # 时长取自该商品,不是全局常量 —— 否则 1 日票也会发 7 天
    ent.expires_at = now + pass_duration(ent.entitlement_type)
    db.commit()
    return ACTIVE, ent


def summary(
    db,
    user_id: str,
    benefits=None,
    *,
    is_guest: bool = False,
    museum=None,
    language: str = "zh",
    preview: bool = False,
) -> dict:
    """前端唯一入口。`can` 是前端该看的东西,其余字段供展示。

    免费层边界(付费墙建在**现场体验**不在内容):
    - 浏览/搜索/完整文字讲解/接地预设问答 → 永远免费,不在 `can` 里体现
    - 识别 → 免费 5 次,用完需通票
    - 语音 → **识别出来的作品**主讲解段免费(见 free_audio_qids),其余需通票

    `can.purchase`:**买票前必须登录**(2026-07-28 定)。通票挂 user_id,而游客
    身份是设备绑定的 —— 游客买了票,换手机/清数据就永久拿不回(收据已消耗,
    恢复购买会命中幂等、不给新用户发权益)。强制登录让权益天然跟着账号走,
    不必再做收据转移。

    [museum] 给了 → `state`/`can.audio_any`/`expires_at` 只看**覆盖这家馆**的票
    (馆内页面用;持巴黎票进荷兰的馆不能显示"通票生效中")。不给 = 任意一张票。
    `passes` 每张票各自的范围与状态,权益页据此写明「哪张票管哪里」。
    """
    state, ent = resolve_state(db, user_id, museum)
    active = state == ACTIVE
    # ⚠️ recognition_quota 是**剩余数**(consume_recognition 每次递减),不是上限。
    # 曾误写成 quota + bonus - used —— 那会重复扣一次 used,少报剩余次数、
    # 让付费墙提前弹(用户初始10次用3次 → 实际剩7,却报成4)。
    quota = getattr(benefits, "recognition_quota", settings.FREE_RECOGNITION_QUOTA)
    bonus = getattr(benefits, "referral_bonus_quota", 0) or 0
    left = max(0, (quota or 0) + bonus)
    unlocked = free_audio_qids(benefits)
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
        # 只含**未过期**的解锁(D8:识别解锁 7 天)。老 App 本地闸按它拦,自然跟着到期。
        "free_audio_qids": unlocked,
        # 加法字段:{qid: 到期时刻},新 App 显示「还剩 X 天」
        "free_audio_until": free_audio_until(benefits),
        # 加法字段(D8 界面):已过期的解锁 + 窗口天数(文案「识别后 N 天内免费听」
        # 的 N 由后端给,改窗口不用发版)
        "free_audio_expired": free_audio_expired(benefits),
        "free_audio_days": FREE_AUDIO_WINDOW.days,
        "passes": _passes(db, user_id, language),
        # 可买的票(加法):不知道用户在哪家馆的购买入口据此列出每一张
        "offers": pass_offers(db, language, preview=preview),
        # ⚠️ **恒为 None**。老字段的语义是"你认领的那一件",而"认领"这件事
        # 已经不存在了(2026-09-19 免费语音改为跟着识别走)。
        # 不删键、恒给 null 是**故意的**:老 App 读到 null 会把本地闸放开、
        # 把判断交回服务端 402 —— 退化方向正确。若在这里回填清单里的第一件,
        # 老 App 反而会把其余已解锁的作品在本地拦掉。
        "free_audio_qid": None,
        "can": {
            "purchase": not is_guest,
            "recognize": active or left > 0,
            # 语音:通票内全放行;免费用户只放行识别解锁过的作品的主讲解段
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
    return [
        {
            "product_id": r.entitlement_type,
            "state": _row_state(r),
            "purchased_at": _iso(r.created_at),
            "activated_at": _iso(r.activated_at),
            "expires_at": _iso(r.expires_at),
        }
        for r in rows
    ]


def _row_state(r) -> str:
    """展示用状态。与 resolve_state 同源的判定,但**逐行**算 ——
    resolve_state 只回答"当前哪张票说了算",历史/权益页要每张票各自的结局。"""
    if r.status not in (ACTIVE, PURCHASED_NOT_ACTIVATED):
        return r.status  # refunded / revoked 原样透出
    if r.status == PURCHASED_NOT_ACTIVATED:
        return EXPIRED if _unactivated_expired(r) else PURCHASED_NOT_ACTIVATED
    exp = _aware(r.expires_at)
    return EXPIRED if exp and exp <= _now() else ACTIVE


def _iso(dt):
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def _passes(db, user_id: str, language: str) -> list[dict]:
    """还能用的票(生效中/待激活),各自带范围名。权益页据此写明
    「荷兰 7 日通票 · 有效至…」「巴黎 7 日通票 · 待激活」—— 用户看得出哪张票管哪里。"""
    rows = (
        db.query(Entitlement)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.status.in_([ACTIVE, PURCHASED_NOT_ACTIVATED]),
        )
        .order_by(Entitlement.created_at.desc())
        .all()
    )
    out = []
    for r in rows:
        state = _row_state(r)
        if state not in (ACTIVE, PURCHASED_NOT_ACTIVATED):
            continue
        out.append(
            {
                "product_id": r.entitlement_type,
                "label": pass_label(r.entitlement_type, language),
                "title": pass_title(r.entitlement_type, language),
                "days": pass_duration(r.entitlement_type).days,
                "state": state,
                "expires_at": _iso(r.expires_at),
                "activate_by": (
                    _iso(activation_deadline(r))
                    if state == PURCHASED_NOT_ACTIVATED
                    else None
                ),
            }
        )
    return out


# D8(spec 2026-09-28 §3.7):音频权利只有「7 天」一个边界。免费识别解锁的主讲解
# 从解锁时刻起 7 天可听;持票期间识别**不写**这里(票本来就覆盖,过期自然锁)。
FREE_AUDIO_WINDOW = timedelta(days=7)


def _free_unlocks(benefits) -> dict[str, datetime | None]:
    """{qid: 解锁时刻}。列存的是 {qid: iso};旧形状是纯 qid 列表(迁移 e6b7 已转换),
    万一还遇到旧列表,时刻记 None = 视为已过期(宁可锁住,不可永久白送)。"""
    raw = getattr(benefits, "free_audio_qids", None) or {}
    if isinstance(raw, list):
        return {q: None for q in raw if q}
    out = {}
    for q, ts in raw.items():
        try:
            out[q] = _aware(datetime.fromisoformat(ts)) if ts else None
        except (TypeError, ValueError):
            out[q] = None
    return out


def free_audio_until(benefits) -> dict[str, str]:
    """未过期的免费解锁 → {qid: 到期时刻 iso}。到期判断**在读取时算**,不靠定时任务。"""
    now = _now()
    return {
        q: (t + FREE_AUDIO_WINDOW).isoformat()
        for q, t in _free_unlocks(benefits).items()
        if t is not None and t + FREE_AUDIO_WINDOW > now
    }


def free_audio_expired(benefits) -> list[str]:
    """解锁过、但 7 天已过的作品。前端据此写明「免费试听已结束」,而不是只弹一个
    不解释原因的付费墙 —— 用户记得自己拍过这件,会以为 App 坏了。"""
    now = _now()
    return [
        q
        for q, t in _free_unlocks(benefits).items()
        if t is None or t + FREE_AUDIO_WINDOW <= now
    ]


def free_audio_qids(benefits) -> list[str]:
    """该用户**当前可听**的免费语音作品(已过 7 天的不算)。行不存在/列为空都返回 []。"""
    return list(free_audio_until(benefits))


def can_play_audio(
    db,
    user_id: str,
    qid: str,
    benefits=None,
    *,
    language: str = "zh",
    section: str = FREE_AUDIO_SECTION,
    museum=None,
) -> bool:
    """某件的语音能不能放。[museum] = 这件作品所属的馆,只认覆盖它的票。

    免费用户:**识别出来的作品**的主讲解段可放(解锁起 7 天内可重播),其余要票。

    [language] 不再参与判断(2026-09-19)。此前免费试听绑死 (作品,语言,段),
    于是用中文识别、事后把 App 换成法语的人会撞 402 —— 他没多拿任何东西,
    只是换了个语言,却被当成第二件。换语言要多一次 TTS 是真的,但上限是
    5 件 × 语言数、且生成一次永久落库(后来的用户白拿缓存),这点钱买不到
    「同一件作品换个语言就要买票」的困惑。参数留着是为了不动调用方签名。
    """
    state, _ = resolve_state(db, user_id, museum)
    if state == ACTIVE:
        return True
    if section != FREE_AUDIO_SECTION:
        return False
    return qid in free_audio_qids(benefits)


def unlock_free_audio(db, user_id: str, qids: list[str]) -> list[str]:
    """识别成功后解锁这些作品的免费语音。返回本次新解锁的 qid。

    调用点是**识别扣费那一处**(recognition/service.py):额度在那里花掉,
    解锁就在那里记账,两件事不分家。

    ⚠️ 与旧的"认领"不同,这里不需要等音频送达 —— 解锁不是一张会被烧掉的券,
    而是"这件你识别过"的事实记录。用户点了一件没音频的作品也不损失什么。

    候选卡的几个候选**全部解锁**:识别没把握时用户更需要听着分辨哪件是对的,
    而这一次识别的额度已经扣了。上限仍由免费识别次数兜住。

    D8:记下解锁时刻,7 天后到期。已过期的件再次被(扣费)识别 → 重新计 7 天。
    ⚠️ 只在**扣了免费额度**的路径上调用;持票识别不写这里。
    """
    if not qids:
        return []
    from app.services.benefits_service import BenefitsService

    benefits = BenefitsService(db).get_or_create_benefits(user_id=user_id)
    live = free_audio_until(benefits)
    added = [q for q in dict.fromkeys(qids) if q and q not in live]
    if not added:
        return []
    now = _now().isoformat()
    unlocks = {
        q: (t.isoformat() if t else None) for q, t in _free_unlocks(benefits).items()
    }
    unlocks.update({q: now for q in added})
    # 整列重新赋值:JSON 列原地改不会被 SQLAlchemy 标记为脏,静默丢更新。
    benefits.free_audio_qids = unlocks
    db.commit()
    return added


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
    museum=None,
) -> str:
    """语音闸门:**付费墙真正生效的地方**(前端 UI 只是它的表达)。

    返回 "allowed" / "denied",**本身不产生副作用**(一个字节都不写):
      allowed   通票生效,或这件是识别解锁过的主讲解段(可无限重播)
      denied    其余 → 端点返 402

    ⚠️ 必须在触发 TTS **之前**调用 —— 否则钱已经花掉了,拦也白拦。

    ⚠️ 曾有第三档 "claimable"(放行 + 音频送达后认领首件),随"免费语音跟着
    识别走"一并删除(2026-09-19)。解锁现在发生在识别扣费那一处,
    闸门不再承担任何写职责 —— 于是"闸门跑在生成之前,而生成可能 404/409/503,
    在闸门里认领会让用户什么都没听到名额却没了"这个历史陷阱从结构上消失了。
    """
    from app.models.user_benefits import UserBenefits

    benefits = db.query(UserBenefits).filter_by(user_id=user_id).one_or_none()
    # ⚠️ benefits 行是**懒建**的,`benefits is None` = 一次都还没用过。
    # 它交给 can_play_audio 判:没有行 → 解锁清单为空 → 免费用户一件都听不了,
    # 而这是对的 —— 一次识别都没做过的人本来就还没解锁任何作品。
    allowed = can_play_audio(
        db, user_id, qid, benefits, language=language, section=section, museum=museum
    )
    return "allowed" if allowed else "denied"
