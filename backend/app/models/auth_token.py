"""一次性账号令牌:找回密码 / 邮箱验证。

**一张表两种用途**(`purpose` 区分)。两者生命周期完全同构 —— 发一串随机字符、
有效期内可用一次、用完作废 —— 分两张表只会让"过期怎么算""用过怎么标"
这类判断各留一份副本,迟早各走各的。

⚠️ **存哈希,不存令牌本身。** 这串东西是账号的万能钥匙:拿到就能改密码。
明文入库意味着**一次只读的泄漏(备份、慢查询日志、只读副本)就等于批量接管账号**。
存 SHA-256 之后,泄漏出去的东西对攻击者没有用。

(不用 bcrypt:令牌是我们生成的 256 位随机数,不是人选的密码,没有字典攻击面;
 而 bcrypt 的"慢"是专为对抗爆破设计的,用在这里只是白白变慢。)
"""

import uuid

from sqlalchemy import Column, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_EMAIL_VERIFY = "email_verify"


class AuthToken(Base):
    """一次性令牌。用过/过期都**不删行** —— 留痕才查得出"这个号被谁重置过"。"""

    __tablename__ = "auth_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False, index=True)
    purpose = Column(String(32), nullable=False)
    # SHA-256 十六进制 = 64 字符。唯一:同一串令牌不可能对应两行。
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # 非空 = 已用过。**用过必须失效**:邮件会一直躺在收件箱里,
    # 可重复使用的重置链接等于账号从此挂着一把永久备用钥匙。
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # 重发时要作废该用户此用途下的旧令牌,按这个索引查
        Index("ix_auth_tokens_user_purpose", "user_id", "purpose"),
    )
