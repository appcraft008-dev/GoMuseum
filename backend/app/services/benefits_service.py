"""
Benefits Service
Handles user recognition quotas, subscriptions, and benefits management
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, ServiceException
from app.models.user_benefits import UserBenefits

logger = logging.getLogger(__name__)


class BenefitsService:
    """Service for managing user benefits and quotas"""

    def __init__(self, db: Session):
        """
        Initialize benefits service

        Args:
            db: Database session
        """
        self.db = db

    def get_or_create_benefits(
        self, user_id: Optional[str] = None, device_id: Optional[str] = None
    ) -> UserBenefits:
        """
        Get existing benefits or create new one

        Args:
            user_id: User identifier (for authenticated users)
            device_id: Device identifier (for anonymous users)

        Returns:
            UserBenefits instance

        Raises:
            ServiceException: If neither user_id nor device_id provided
        """
        if not user_id and not device_id:
            raise ServiceException("Either user_id or device_id must be provided")

        # Try to find existing benefits
        query = self.db.query(UserBenefits)

        if user_id:
            benefits = query.filter(UserBenefits.user_id == user_id).first()
        else:
            benefits = query.filter(UserBenefits.device_id == device_id).first()

        if benefits:
            logger.info(
                f"Found existing benefits for user_id={user_id}, device_id={device_id}"
            )
            return benefits

        # Create new benefits with default free tier
        logger.info(
            f"Creating new benefits for user_id={user_id}, device_id={device_id}"
        )

        benefits = UserBenefits(
            user_id=user_id,
            device_id=device_id,
            recognition_quota=5,  # Free tier: 5 recognitions
            is_premium=False,
            day_pass_active=False,
            referral_bonus_quota=0,
            total_recognitions_used=0,
        )

        self.db.add(benefits)
        self.db.commit()
        self.db.refresh(benefits)

        return benefits

    def check_access(
        self, user_id: Optional[str] = None, device_id: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Check if user has recognition access

        Args:
            user_id: User identifier
            device_id: Device identifier

        Returns:
            Dictionary with access status and quota information
        """
        benefits = self.get_or_create_benefits(user_id, device_id)

        has_access = benefits.has_access()
        total_quota = benefits.recognition_quota + benefits.referral_bonus_quota

        return {
            "has_access": has_access,
            "recognition_quota": benefits.recognition_quota,
            "referral_bonus_quota": benefits.referral_bonus_quota,
            "total_quota": total_quota,
            "is_premium": benefits.is_premium,
            "day_pass_active": benefits.day_pass_active,
            "total_used": benefits.total_recognitions_used,
            "premium_expires_at": (
                benefits.premium_expires_at.isoformat()
                if benefits.premium_expires_at
                else None
            ),
            "day_pass_expires_at": (
                benefits.day_pass_expires_at.isoformat()
                if benefits.day_pass_expires_at
                else None
            ),
        }

    def consume_recognition(
        self, user_id: Optional[str] = None, device_id: Optional[str] = None
    ) -> bool:
        """
        Consume one recognition from user's quota

        Args:
            user_id: User identifier
            device_id: Device identifier

        Returns:
            True if successfully consumed, False if no quota

        Raises:
            ServiceException: If consumption fails
        """
        try:
            benefits = self.get_or_create_benefits(user_id, device_id)

            success = benefits.consume_recognition()

            if success:
                self.db.commit()
                logger.info(
                    f"Recognition consumed for user_id={user_id}, device_id={device_id}"
                )
            else:
                logger.warning(
                    f"No quota available for user_id={user_id}, device_id={device_id}"
                )

            return success

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to consume recognition: {str(e)}")
            raise ServiceException(f"Failed to consume recognition: {str(e)}")

    def add_recognition_pack(
        self,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        quantity: int = 10,
    ):
        """
        Add recognition pack to user's quota

        Args:
            user_id: User identifier
            device_id: Device identifier
            quantity: Number of recognitions to add (default 10)
        """
        benefits = self.get_or_create_benefits(user_id, device_id)
        benefits.recognition_quota += quantity
        self.db.commit()

        logger.info(f"Added {quantity} recognitions for user_id={user_id}")

    def activate_day_pass(
        self, user_id: Optional[str] = None, device_id: Optional[str] = None
    ):
        """
        Activate 24-hour day pass

        Args:
            user_id: User identifier
            device_id: Device identifier
        """
        benefits = self.get_or_create_benefits(user_id, device_id)

        benefits.day_pass_active = True
        benefits.day_pass_expires_at = datetime.utcnow() + timedelta(days=1)
        self.db.commit()

        logger.info(f"Day pass activated for user_id={user_id}")

    def activate_premium(
        self,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        duration_days: int = 365,
    ):
        """
        Activate premium subscription

        Args:
            user_id: User identifier
            device_id: Device identifier
            duration_days: Subscription duration (default 365 days)
        """
        benefits = self.get_or_create_benefits(user_id, device_id)

        benefits.is_premium = True
        benefits.premium_expires_at = datetime.utcnow() + timedelta(days=duration_days)
        self.db.commit()

        logger.info(
            f"Premium activated for user_id={user_id}, duration={duration_days} days"
        )

    def add_referral_bonus(
        self,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        bonus_quota: int = 5,
    ):
        """
        Add referral bonus recognitions

        Args:
            user_id: User identifier
            device_id: Device identifier
            bonus_quota: Bonus recognitions to add
        """
        benefits = self.get_or_create_benefits(user_id, device_id)
        benefits.referral_bonus_quota += bonus_quota
        self.db.commit()

        logger.info(f"Added {bonus_quota} referral bonus for user_id={user_id}")


def get_benefits_service(db: Session) -> BenefitsService:
    """
    Create BenefitsService instance with database session

    Args:
        db: Database session

    Returns:
        BenefitsService instance
    """
    return BenefitsService(db)
