"""
User Benefits Model
SQLAlchemy model for user subscription and recognition benefits
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def _free_quota() -> int:
    """免费额度默认值(延迟读 settings,便于测试覆盖)。"""
    from app.core.config import settings

    return settings.FREE_RECOGNITION_QUOTA


class UserBenefits(Base):
    """
    Model for storing user benefits and subscription status

    Attributes:
        id: Unique identifier (UUID)
        user_id: User identifier (for future user system integration)
        device_id: Device identifier for anonymous users
        recognition_quota: Remaining recognition quota
        is_premium: Whether user has premium subscription
        premium_expires_at: Premium subscription expiration date
        day_pass_expires_at: Day pass expiration date
        total_recognitions_used: Total recognitions performed
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "user_benefits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # User identification (support both authenticated and anonymous users)
    user_id = Column(String(255), nullable=True, index=True, unique=True)
    device_id = Column(String(255), nullable=True, index=True)

    # Recognition quota
    # 剩余识别次数(每次识别递减,不是上限)。默认值见 settings.FREE_RECOGNITION_QUOTA
    recognition_quota = Column(Integer, nullable=False, default=lambda: _free_quota())
    total_recognitions_used = Column(Integer, nullable=False, default=0)

    # Premium subscription
    is_premium = Column(Boolean, nullable=False, default=False)
    premium_expires_at = Column(DateTime, nullable=True)

    # Day pass
    day_pass_active = Column(Boolean, nullable=False, default=False)
    day_pass_expires_at = Column(DateTime, nullable=True)

    # Referral rewards
    referral_bonus_quota = Column(Integer, nullable=False, default=0)
    # 首件免费语音:按**作品**认领(非 section、非"一次待花的券")。
    # 认领时机=首次识别成功后自动播放,保证每个免费用户都体验过语音。
    free_audio_qid = Column(String(64), nullable=True)
    # 免费试听收敛到 (作品, 语言, 主讲解段):一件作品有多段、每段独立 TTS,
    # 再乘 10 种语言 —— 只记 qid 的话"免费一件"实际是几十次生成。
    free_audio_lang = Column(String(16), nullable=True)
    free_audio_claimed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<UserBenefits(id={self.id}, quota={self.recognition_quota}, "
            f"premium={self.is_premium})>"
        )

    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "device_id": self.device_id,
            "recognition_quota": self.recognition_quota,
            "is_premium": self.is_premium,
            "premium_expires_at": (
                self.premium_expires_at.isoformat() if self.premium_expires_at else None
            ),
            "day_pass_active": self.day_pass_active,
            "day_pass_expires_at": (
                self.day_pass_expires_at.isoformat()
                if self.day_pass_expires_at
                else None
            ),
            "referral_bonus_quota": self.referral_bonus_quota,
            "total_recognitions_used": self.total_recognitions_used,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def has_access(self) -> bool:
        """Check if user has recognition access"""
        now = datetime.utcnow()

        # Check day pass
        if (
            self.day_pass_active
            and self.day_pass_expires_at
            and self.day_pass_expires_at > now
        ):
            return True

        # Check premium subscription
        if (
            self.is_premium
            and self.premium_expires_at
            and self.premium_expires_at > now
        ):
            return True

        # Check quota (including referral bonus)
        total_quota = self.recognition_quota + self.referral_bonus_quota
        if total_quota > 0:
            return True

        return False

    def consume_recognition(self) -> bool:
        """
        Consume one recognition from user's quota

        Returns:
            True if successfully consumed, False if no quota available
        """
        now = datetime.utcnow()

        # Day pass or premium: unlimited recognitions
        if (
            self.day_pass_active
            and self.day_pass_expires_at
            and self.day_pass_expires_at > now
        ) or (
            self.is_premium
            and self.premium_expires_at
            and self.premium_expires_at > now
        ):
            self.total_recognitions_used += 1
            return True

        # Use referral bonus quota first
        if self.referral_bonus_quota > 0:
            self.referral_bonus_quota -= 1
            self.total_recognitions_used += 1
            return True

        # Use regular quota
        if self.recognition_quota > 0:
            self.recognition_quota -= 1
            self.total_recognitions_used += 1
            return True

        return False
