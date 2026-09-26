"""音频失效台账:每一条「已有音频的 key 被清空/被删」都在这里留一行。

为什么需要(契约纪律 37,2026-09-26 跨馆作者事故):`generate --force` 两次顺带清掉了
跨馆作者的简介音频,9-14 那次 12 天没人发现,原文也过了备份保留期找不回。
音频文件其实都还在 R2 —— 丢的是「这个 key 属于谁、念的是哪段文字」。
这张表把这两样留下来:丢了可以照着挂回去,GC 也能据此不删它们。

写入点只有一个:`app.services.audio_guard`(挂在 SessionLocal 的 before_flush 上),
所以任何代码路径清掉音频都会被记下,不依赖调用方记得写。
"""

import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class AudioInvalidation(Base):
    __tablename__ = "audio_invalidations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # section | qa | artist_bio
    entity = Column(String(16), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # section/qa
    artist_qid = Column(String(32), nullable=True, index=True)  # artist_bio
    language = Column(String(8), nullable=True)
    section_code = Column(String(32), nullable=True)  # section
    qa_sort = Column(Integer, nullable=True)  # qa
    audio_key = Column(Text, nullable=False, index=True)
    audio_engine = Column(String(32), nullable=True)
    # 失效那一刻音频对应的文字 —— 有它才能判断「挂回去对不对得上」
    old_text = Column(Text, nullable=True)
    # delete | cleared(置空) | removed(bio_audio 字典里少了这个语种)
    change = Column(String(16), nullable=False)
    command = Column(Text, nullable=True)  # 进程 argv,追溯是哪条命令
    allowed = Column(String(16), nullable=False)  # record_only | allowed
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
