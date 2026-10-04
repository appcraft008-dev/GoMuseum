"""退役的 is_premium / day_pass_* 不再给不限次识别。

2026-10-05 实例:测试账号带着 is_premium=True(到 2126 年),巴黎通票过期后
仍在卢浮宫无限识别、逐件解锁语音 —— 权益真相源只能是 entitlements 表。
"""

from datetime import datetime, timedelta

from app.models.user_benefits import UserBenefits


def _legacy(quota):
    far = datetime.utcnow() + timedelta(days=365)
    return UserBenefits(
        recognition_quota=quota,
        referral_bonus_quota=0,
        total_recognitions_used=0,
        is_premium=True,
        premium_expires_at=far,
        day_pass_active=True,
        day_pass_expires_at=far,
    )


def test_legacy_flags_do_not_grant_access():
    assert _legacy(0).has_access() is False
    assert _legacy(0).consume_recognition() is False


def test_legacy_flags_do_not_skip_decrement():
    b = _legacy(2)
    assert b.consume_recognition() is True
    assert b.recognition_quota == 1
