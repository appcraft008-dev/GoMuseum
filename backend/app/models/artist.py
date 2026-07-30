"""作者一等实体:按 artist QID 生成一次的规范作者介绍,同作者作品复用。"""

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import JSON

from app.core.database import Base


class Artist(Base):
    __tablename__ = "artists"

    qid = Column(String(32), primary_key=True)
    name_zh = Column(String(255), nullable=True)
    name_en = Column(String(255), nullable=True)
    birth = Column(String(16), nullable=True)
    death = Column(String(16), nullable=True)
    nationality = Column(String(128), nullable=True)
    notable_works = Column(
        MutableList.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )
    bio = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )
    bio_audio = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )  # {lang: audio_key} 作者介绍音频,按作者共享一份(TTS Phase2)
    # {lang: engine} 与 bio_audio **同进同退**:哪条 key 是哪个引擎生成的。
    # 音频 key 存在三处,这是最容易被漏掉的一处 —— 没有它,作者介绍既进不了
    # 迁移队列也不进覆盖率报表,自托管替换完会残留旧音色(而 bio 按作者共享,
    # 一条音频在该作者所有作品下播放)。
    bio_audio_engine = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )
    name_i18n = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )  # {lang: name} 多语显示名
    nationality_i18n = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )  # {lang: 国籍}(P27 权威标签→翻译兜底;交接③)
    notable_works_i18n = Column(
        MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql")), nullable=True
    )  # {lang: [代表作名]}(P800 权威标签→翻译兜底)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
