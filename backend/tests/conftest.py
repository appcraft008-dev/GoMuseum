"""Pytest 全局配置：测试环境关闭速率限制"""

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "0")


def account_tables():
    """删号路径会碰到的全部表。

    这些 fixture 用 SQLite 只建"本用例涉及的表"(个别模型的 server_default NOW()
    不兼容 SQLite，不能 create_all 全量)。但删号是横跨多张表的一个动作，
    各 fixture 手抄一份清单的话，**下次给删号加一张表就会在别处静默炸掉** ——
    #585 就是这么炸的：加了 feedbacks 后 `test_password_reset` 的 fixture 缺这张表，
    而本地只跑改动到的那两个文件根本看不见。

    所以清单在这里只有一份，凡是会走到 `delete_user_account` 的 fixture 都用它。
    给删号新加表时改这里，不必去找有哪些 fixture 抄过。
    """
    from app.models.auth_token import AuthToken
    from app.models.feedback import Feedback
    from app.models.purchase import Entitlement, Purchase
    from app.models.recognition_event import RecognitionEvent
    from app.models.user import User
    from app.models.user_benefits import UserBenefits

    return [
        User.__table__,
        UserBenefits.__table__,
        AuthToken.__table__,
        Purchase.__table__,
        Entitlement.__table__,
        RecognitionEvent.__table__,
        Feedback.__table__,
    ]
