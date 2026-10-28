"""必看勋章:某用户在某馆打满一轮必看的记录(spec 2026-10-27 必看打卡 §五.3)。

打满那一刻落一行,之后清单怎么改、足迹怎么删都不动它。含用户标识:
导出(export_user_data)给出,删号(delete_user_account)真删。
"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class MustSeeMedal(Base):
    __tablename__ = "must_see_medals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False)
    museum_slug = Column(String(64), nullable=False)
    # 这一轮补齐最后一件的那次打卡时间(UTC,不带时区,同 recognition_events.created_at)
    completed_at = Column(DateTime, nullable=False)
    # 完成时清单的件数(勋章上写「12/12」)
    count = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        # 并发的两个请求算出的完成时刻相同 → 只落一行
        UniqueConstraint("user_id", "museum_slug", "completed_at"),
        Index("ix_must_see_medals_user_museum", "user_id", "museum_slug"),
    )
