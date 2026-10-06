"""S5 识别照片反馈(spec 2026-10-05 §四 S5)。

**照片只当信号不当资产**(用户 2026-10-05 定):只用于补录未收录作品、给无图作品找授权图
并核对、诊断识别失败原因。绝不入识别库、绝不对外展示;≤90 天或处理完即删(取先到);
删号即删。删后只留不含图像的元数据(分数/答案/归因标签)。

不复用 `feedbacks`:有图片、有分诊状态、有 90 天生命周期。"""

import uuid

from sqlalchemy import JSON, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base

TRIGGERS = ("found", "not_found", "corrected")
TRIAGES = ("fixed_now", "no_reference", "real_failure")
KEY_PREFIX = "recognition-feedback/"
RETENTION_DAYS = 90
TEXT_MAX = 1000


class RecognitionPhotoFeedback(Base):
    __tablename__ = "recognition_photo_feedbacks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # 同 feedbacks:令牌解析得出才填 user_id,前端不传
    user_id = Column(String(255), nullable=True, index=True)
    device_id = Column(String(255), nullable=True, index=True)

    phash = Column(String(64), nullable=False, index=True)
    museum_slug = Column(String(64), nullable=True)
    language = Column(String(8), nullable=True)
    app_version = Column(String(64), nullable=True)
    engine_model = Column(String(64), nullable=True)

    trigger = Column(String(16), nullable=False, index=True)  # TRIGGERS
    answer_qid = Column(String(32), nullable=True, index=True)  # not_found 为空
    query_text = Column(Text, nullable=True)  # 用户在选择页搜的词
    label_text = Column(Text, nullable=True)  # 说明牌转写
    # 服务端按 phash 查最近识别事件得出(不收客户端传的)
    server_result = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    text = Column(Text, nullable=True)  # 选填补充文字

    image_key = Column(String(255), nullable=True)  # 私有桶 key;删图后置空
    triage = Column(String(16), nullable=True, index=True)  # TRIAGES(自动分诊)
    cause = Column(String(64), nullable=True)  # 人工归因标签
    status = Column(
        String(16), nullable=False, server_default="new", default="new", index=True
    )  # new → triaged → done
