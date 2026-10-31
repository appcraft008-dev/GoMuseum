"""付费漏斗埋点(P0-c,2026-07-27)。

**只做 12 个核心事件,不做 30 个** —— 埋点太多让分析变难不是变易。
这 12 个刚好回答:识别→额度耗尽→付费页→购买→激活→跨馆使用 这条链,
以及"用户究竟为什么付费"(trigger)。其余等有真实流量再加。

不建后台,靠 `ops_report.py` 出数(见 [[monetization-plan]])。
"""

import uuid

from sqlalchemy import JSON, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base

# 核心事件(改这里前先问:少了它哪个问题答不了?)
EVENTS = (
    # 识别漏斗
    "recognition_succeeded",
    "free_quota_exhausted",
    # 三类付费墙曝光(分开记才知道哪个墙有效)
    "paywall_viewed_from_audio",
    "paywall_viewed_from_quota",
    "paywall_viewed_from_ai",
    # 购买链路
    "purchase_started",
    "purchase_succeeded",
    "purchase_failed",
    "purchase_refunded",
    "pass_activated",
    "pass_exchanged",  # 未激活票换城市:多了说明用户常买错,该回头看购买入口
    # 内容入口(判断"搜索绕过付费"是否成立的关键)
    "content_viewed",
    # 跨馆复用(MVP 最重要的新指标)
    "museum_used",
    # 首件免费语音
    "free_audio_played",
    # 免费额度发放(刷额度的形态=同 IP 大量新游客;device_id 客户端可控,
    # 不做 IP 封堵——博物馆共享 WiFi 会误伤真实用户,先观测再决定)
    "guest_created",
    # 分享落地页被看(props.source=app 是 App 分享来的,direct 是其余)。
    # 回答的问题:分享这条获客渠道有没有人进来 —— ≥100 真实活跃用户前别看(spec §八)。
    # 分享次数 ≈ card.jpg 的 nginx 访问量,不另设事件。
    "share_page_view",
    # V78(10-31):讲解长度是否合适、两种音色真实用户有无差异、深度段有没有人听。
    # 每次暂停/播完/切走/退出一条,同一次收听按 props.session 取最大 played_s
    "audio_played",
    # V78(10-31):讲解末尾 👍/👎;按懒生成/预生成、引擎、语种比满意率,单件攒不起数
    "content_rated",
)

# 容量监控事件(spec 2026-10-21-elastic-scaling-design §7;阶段 0)。不是付费漏斗,
# 别并进 EVENTS。props 约定见 docs/superpowers/plans/2026-10-23-elastic-stage0.md 事件表。
OPS_EVENTS = (
    "lazy_slot_full",  # 懒生成/懒翻译拿不到进程名额(同一件 10 分钟一条)→ 阶段 1 触发
    "lazy_fanout_slot_full",  # 补语言拿不到进程名额 → 阶段 1 触发
    "lazy_started",  # 懒生成开工;running = 全站同时在生成的件数 → 阶段 3 触发
    "lazy_finished",  # 懒生成结束(ok/err_kind/各语言段数)→ 生成失败告警
    "lazy_cap_hit",  # 每账号/每 IP 日额度用尽(layer/tier)→ 评估放宽 IP 额度
    "tts_busy",  # 本进程同时合成 ≥4 路(每分钟一条)→ 阶段 2 触发
    "ops_sample",  # ops_check 每 5 分钟的采样
    "ops_alert",  # ops_check 发出(或只记不发)的告警,也是限频的依据
    "probe_login",  # 从 Google 网段登录(Play 审核/预发布测试机)→ 报告剔出真实用户
    "tester_mark",  # 自己人的账号/设备(scripts/mark_testers.py 或从 OPS_TESTER_IPS 登录)
)


class AppEvent(Base):
    """一行一个事件。刻意保持窄表 + JSONB props,加事件不用改结构。"""

    __tablename__ = "app_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=True, index=True)
    device_id = Column(String(255), nullable=True, index=True)
    name = Column(String(64), nullable=False, index=True)
    museum_slug = Column(String(64), nullable=True, index=True)
    # 自由维度:content_viewed 的 from=search|recognition|collection|directory;
    # purchase_succeeded 的 trigger=audio|quota|ai;paywall 的 qid 等
    # JSONB 在 Postgres 用原生类型,其他方言(测试用 SQLite)回落 JSON
    props = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
