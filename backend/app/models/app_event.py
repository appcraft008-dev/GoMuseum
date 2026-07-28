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

# 14 个核心事件(改这里前先问:少了它哪个问题答不了?)
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
    # 内容入口(判断"搜索绕过付费"是否成立的关键)
    "content_viewed",
    # 跨馆复用(MVP 最重要的新指标)
    "museum_used",
    # 首件免费语音
    "free_audio_played",
    # 免费额度发放(刷额度的形态=同 IP 大量新游客;device_id 客户端可控,
    # 不做 IP 封堵——博物馆共享 WiFi 会误伤真实用户,先观测再决定)
    "guest_created",
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
