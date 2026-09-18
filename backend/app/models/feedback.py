"""用户反馈(2026-09-18)。内容质量的兜底环 —— 见 CLAUDE.md「AI 内容质量原则」:
`人只审形式安全,不审事实对错;错漏靠用户反馈兜底`。

生成侧的闸(接地/忠实度/语言一致性/锐度/响度)都建了,这是消费侧唯一的入口。

**不塞进 `app_events`**:那张表是纯分析窄表,`log_event` 的纪律是「记账失败绝不
破坏业务」→ 异常静默吞掉。对埋点合理,对反馈是错的 —— 用户点了提交、后端悄悄
丢了,必须让他知道。而且反馈有自由文本和**处理状态**,混进分析表会把它搞脏。

**也不复用 `recognition_demands`**:那张表是 (museum, phash) 去重聚合 + hit_count,
语义是"同一张图再来一次 = 已有需求 +1",不支持逐条存、逐条读、逐条流转状态。
"""

import uuid

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

# 藏品级:用户能**感知到的现象**,不是技术分层。
# 绝不让用户选「文本问题 vs 音频问题」—— 他不懂这个分层,而且会选错:
# 繁体念错那次文本是对的、TTS 念错了,用户只会说"读得很怪"。
OBJECT_KINDS = ("content_wrong", "audio_bad", "audio_missing", "other")
APP_KINDS = ("app_crash", "recognition_bad", "feature_request", "other")
ALL_KINDS = tuple(sorted(set(OBJECT_KINDS) | set(APP_KINDS)))

SCOPES = ("object", "app")

TEXT_MAX = 1000


class Feedback(Base):
    """一条反馈一行。逐条可读、可流转状态,不做去重聚合。

    ⚠️ 去重发生在**读侧**(`scripts/feedback_report.py` 按不同 device_id 计数),
    不在写侧。双击提交/超时重试会造重复行,而"第三个人报同一件事就浮上来"
    这个排序机制数的应该是**多少人报过**,不是多少行。写侧加幂等键更贵且更不准。
    """

    __tablename__ = "feedbacks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # 匿名可写:游客也要能反馈 —— 最需要反馈的时刻往往正是游客态。
    # user_id 是已登录时后端从令牌取的,前端不传(传了也不信)。
    user_id = Column(String(255), nullable=True, index=True)
    device_id = Column(String(255), nullable=True, index=True)

    scope = Column(String(16), nullable=False, index=True)  # object | app

    # 坐标:scope=object 时必填。用户不填这些,全部由客户端自动附带。
    museum_slug = Column(String(64), nullable=True, index=True)
    qid = Column(String(32), nullable=True, index=True)
    # 🔴 前端必须传 **API 语言参数**(繁体是 `zh-hant` 不是 `zh`),不是 UI locale。
    # 10 语 = 10 份独立内容(独立生成/翻译/音频),带错语种 = 修错行。
    language = Column(String(8), nullable=True, index=True)

    kind = Column(String(32), nullable=False, index=True)
    text = Column(Text, nullable=True)

    app_version = Column(String(64), nullable=True)
    platform = Column(String(16), nullable=True)

    # new -> triaged -> done。不建后台,靠 SQL 改(同 app_events 的惯例)。
    status = Column(
        String(16), nullable=False, server_default="new", default="new", index=True
    )
