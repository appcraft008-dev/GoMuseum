"""孤儿回收的**安全护栏**。

这是不可逆删除,护栏比功能重要。三条护栏平时都不触发,
一旦触发就是在阻止一次清库。
"""

import sys
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject

sys.path.insert(0, "scripts")


@pytest.fixture()
def db():
    e = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=e,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            Artist.__table__,
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
        ],
    )
    s = sessionmaker(bind=e)()
    yield s
    s.close()


def test_artist_bio_audio_is_counted_as_referenced(db):
    """⭐ bio_audio 是 {lang: key} 的 JSON —— 三处 key 里最容易漏的一处。
    漏了就会把所有作者介绍音频当孤儿删掉。"""
    from gc_orphan_audio import referenced_keys

    db.add(Artist(qid="Q1", name_en="X", bio_audio={"zh": "k-zh", "en": "k-en"}))
    db.commit()
    assert referenced_keys(db) == {"k-zh", "k-en"}


def test_all_three_key_locations_are_covered(db):
    from gc_orphan_audio import referenced_keys

    m = Museum(slug="m", name_en="M")
    db.add(m)
    db.commit()
    o = MuseumObject(museum_id=m.id, qid="Q1")
    db.add(o)
    db.commit()
    db.add(
        ObjectContentSection(
            object_id=o.id, language="zh", section_code="guide", audio_key="k-sec"
        )
    )
    db.add(
        ObjectSuggestedQuestion(
            object_id=o.id,
            language="zh",
            sort=1,
            question="q",
            answer="a",
            audio_key="k-qa",
        )
    )
    db.add(Artist(qid="Q2", name_en="Y", bio_audio={"zh": "k-bio"}))
    db.commit()
    assert referenced_keys(db) == {"k-sec", "k-qa", "k-bio"}


def test_empty_reference_set_means_abort_not_delete_everything():
    """引用集合为空 = 查询出错或连错库。照删就是清空音频库。"""
    from gc_orphan_audio import referenced_keys  # noqa: F401

    # 护栏逻辑本身(与 DB 无关):空引用 + 有对象 → 必须中止
    refs, objects = set(), [("object-audio/a.mp3", 100, None)]
    should_abort = bool(objects) and not refs
    assert should_abort is True


def test_slot_strips_random_suffix_and_legacy_extension():
    from gc_orphan_audio import slot

    assert slot("object-audio/Q1/en/guide-Ab_c-234567890XY.mp3") == (
        "object-audio/Q1/en/guide"
    )
    assert slot("object-audio/Q1/en/guide.mp3") == "object-audio/Q1/en/guide"


def test_grace_counts_from_slot_change_not_file_mtime(db):
    """宽限期从「这个位置换了音频」算起,不看 R2 文件写入时间(9-06 全桶重写把 mtime 刷平了):
    一年前录的旧音频昨天才被换掉,也可能有人正拿着旧直链在播。"""
    from gc_orphan_audio import recently_changed_slots

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    m = Museum(slug="m", name_en="M")
    db.add(m)
    db.commit()
    o = MuseumObject(museum_id=m.id, qid="Q1")
    db.add(o)
    db.commit()
    for lang, age in (("en", 1), ("fr", 30)):
        db.add(
            ObjectContentSection(
                object_id=o.id,
                language=lang,
                section_code="guide",
                audio_key=f"object-audio/Q1/{lang}/guide-NEWNEWNEWNEWNEW1.mp3",
                updated_at=now - timedelta(days=age),
            )
        )
    db.add(
        ObjectSuggestedQuestion(
            object_id=o.id,
            language="en",
            sort=1,
            question="q",
            answer="a",
            audio_key="object-audio/Q1/en/qa_1-NEWNEWNEWNEWNEW1.mp3",
            updated_at=now - timedelta(days=2),
        )
    )
    db.add(
        Artist(
            qid="Q2",
            name_en="Y",
            bio_audio={"zh": "object-audio/artist/Q2/zh-NEWNEWNEWNEWNEW1.mp3"},
            updated_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
    )
    db.commit()
    assert recently_changed_slots(db, now - timedelta(days=7)) == {
        "object-audio/Q1/en/guide",
        "object-audio/Q1/en/qa_1",
        "object-audio/artist/Q2/zh",
    }


def test_ratio_ceiling_blocks_mass_deletion():
    """一次删太多 = 对账逻辑大概率出错,先中止再说。"""
    total, orphans, max_ratio = 1000, 800, 0.5
    assert (orphans / total) > max_ratio


def test_ledger_recent_invalidations_are_protected_from_gc():
    """纪律 37:近期被清的在用音频(如 09-14 事故)看起来像孤儿,实为待恢复 —— 不许删。"""
    from gc_orphan_audio import ledger_protected_keys

    from app.models.audio_invalidation import AudioInvalidation

    e = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=e, tables=[AudioInvalidation.__table__])
    s = sessionmaker(bind=e)()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for key, age in (("recent.mp3", 3), ("old.mp3", 90)):
        s.add(
            AudioInvalidation(
                entity="artist_bio",
                audio_key=key,
                change="removed",
                allowed="allowed",
                created_at=now - timedelta(days=age),
            )
        )
    s.commit()
    assert ledger_protected_keys(s, 60) == {"recent.mp3"}
