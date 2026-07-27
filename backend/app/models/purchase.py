"""内购订单与时长权益(收费模式定案 2026-07-27)。

两张表分工:
- `purchases`  —— 商店那侧发生了什么(对账/退款/恢复购买/防重复发放)
- `entitlements` —— 用户现在有什么权(激活态/到期/来源订单)

**不建按馆权益**:通票按「时长 × 地理范围」而非按馆(加馆不增 SKU、无需差价升级)。
scope 先只有 "paris",将来 madrid/london/europe 自然扩展,不改表结构。
"""

import uuid

from sqlalchemy import Column, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Purchase(Base):
    """商店订单流水。一次支付一行,退款/撤销只改状态不删行(对账要留痕)。"""

    __tablename__ = "purchases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    platform = Column(String(16), nullable=False)  # google|apple
    product_id = Column(String(128), nullable=False)  # paris_pass_7d
    # 商店交易号:唯一,防同一笔重复发放权益(恢复购买会重复上报同一 token)
    store_transaction_id = Column(String(255), nullable=False, unique=True, index=True)
    original_transaction_id = Column(String(255), nullable=True, index=True)
    amount = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(8), nullable=True)
    # purchased|refunded|revoked —— 不用布尔,退款/撤销语义不同(前者用户发起,后者商店/我们)
    status = Column(String(16), nullable=False, default="purchased", index=True)
    purchased_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    receipt_payload = Column(Text, nullable=True)  # 原始收据,存档待查
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Entitlement(Base):
    """用户持有的时长权益。

    ⭐ **购买后不立即计时**:旅游产品用户常提前几天买,立即计时会白白烧掉有效期。
    购买 → `purchased_not_activated`;首次使用高级功能且**用户显式确认**后才
    `active` 并开始连续 7×24h(静默激活=误触即烧,是差评来源)。
    """

    __tablename__ = "entitlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    entitlement_type = Column(String(64), nullable=False)  # paris_pass_7d
    scope = Column(String(32), nullable=False, default="paris")  # 地理范围,不是馆
    source_purchase_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    # purchased_not_activated|active|expired|refunded|revoked
    status = Column(
        String(32), nullable=False, default="purchased_not_activated", index=True
    )
    activated_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    granted_reason = Column(String(64), nullable=True)  # purchase|beta|compensation
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
