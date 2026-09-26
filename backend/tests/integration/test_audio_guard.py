"""音频损失闸(契约纪律 37 第①②层)。

2026-09-14 / 09-26 两次 `generate --force` 顺带清掉跨馆作者简介音频,第一次 12 天没人
发现。这里的用例直接复现那两种写法,证明闸会拦;同时钉住「不该拦的不能拦」
(tts-1 → VoxCPM2 换 key、新行、无音频的正常改写),否则闸会被人嫌吵而拆掉。
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import StaticPool

from app.core.database import Base, audio_loss_guard
from app.models.artist import Artist
from app.models.audio_invalidation import AudioInvalidation
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services import audio_guard
from app.services.audio_guard import AudioLossBlocked
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture(autouse=True)
def _policy():
    audio_guard._reset_for_tests()
    yield
    audio_guard._reset_for_tests()


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
            AudioInvalidation.__table__,
        ],
    )
    Factory = sessionmaker(bind=engine)
    event.listen(Factory, "before_flush", audio_loss_guard)  # 同 SessionLocal
    s = Factory()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language="zh",
            section_code="guide",
            body="旧正文。",
            status="published",
            audio_key="object-audio/Q1/zh-guide.mp3",
            audio_engine="voxcpm2",
        )
    )
    s.add(
        ObjectSuggestedQuestion(
            object_id=o.id,
            language="zh",
            sort=0,
            question="问?",
            answer="答。",
            status="published",
            audio_key="object-audio/Q1/zh-qa0.mp3",
        )
    )
    s.add(
        Artist(
            qid="Q34618",
            name_en="Gustave Courbet",
            bio={"en": "Courbet bio.", "zh": "库尔贝简介。"},
            bio_audio={
                "en": "object-audio/artist/Q34618/en.mp3",
                "zh": "object-audio/artist/Q34618/zh.mp3",
            },
            bio_audio_engine={"en": "voxcpm2", "zh": "voxcpm2"},
        )
    )
    s.commit()
    yield s
    s.close()


def _section(db):
    return db.query(ObjectContentSection).filter_by(language="zh").one()


def test_clearing_section_audio_is_blocked_and_nothing_is_written(db):
    _section(db).audio_key = None
    with pytest.raises(AudioLossBlocked):
        db.commit()
    db.rollback()
    assert _section(db).audio_key == "object-audio/Q1/zh-guide.mp3"
    assert db.query(AudioInvalidation).count() == 0


def test_generate_force_body_rewrite_path_is_blocked(db):
    """09-26 那条路:重生成改了正文 → _upsert_section 清 audio_key。"""
    from app.services.content_repo import persist_generated_sections

    with pytest.raises(AudioLossBlocked):
        persist_generated_sections(db, "Q1", "zh", {"guide": "新正文。"})


def test_shared_artist_bio_audio_removal_is_blocked(db):
    """09-14 / 09-26 那条路:作者简介重写时 pop 掉 bio_audio 的语种。"""
    art = db.query(Artist).filter_by(qid="Q34618").one()
    art.bio_audio = {"en": art.bio_audio["en"]}  # zh 被去掉
    with pytest.raises(AudioLossBlocked):
        db.commit()


def test_in_place_mutation_with_flag_modified_is_also_caught(db):
    """JSON 原地改 + flag_modified 时 ORM 历史里没有旧值 —— 闸读库比对,照样拦。"""
    art = db.query(Artist).filter_by(qid="Q34618").one()
    art.bio_audio.pop("zh")
    flag_modified(art, "bio_audio")
    with pytest.raises(AudioLossBlocked):
        db.commit()


def test_replacing_qa_with_audio_is_blocked(db):
    """persist_suggested_questions 原来用批量 delete,绕过 session 事件 —— 已改逐行删。"""
    from app.services.content_repo import persist_suggested_questions

    with pytest.raises(AudioLossBlocked):
        persist_suggested_questions(
            db, "Q1", "zh", [{"question": "新?", "answer": "新。"}]
        )


def test_blocked_error_is_not_swallowed_by_except_exception(db):
    """管线里到处是 except Exception: continue —— 普通异常会被吞掉、批任务照样跑完。"""
    _section(db).audio_key = None
    swallowed = False
    with pytest.raises(AudioLossBlocked):
        try:
            db.commit()
        except Exception:
            swallowed = True
    assert not swallowed


def test_explicit_allowance_passes_and_leaves_a_recoverable_ledger(db):
    audio_guard.allow(1)
    _section(db).audio_key = None
    db.commit()
    led = db.query(AudioInvalidation).one()
    assert led.audio_key == "object-audio/Q1/zh-guide.mp3"
    assert led.old_text == "旧正文。" and led.audio_engine == "voxcpm2"
    assert (
        led.entity == "section" and led.change == "cleared" and led.allowed == "allowed"
    )


def test_allowance_is_a_budget_not_a_switch(db):
    """放行 1 条,第 2 条仍拦 —— 防止「放行一次」变成「这个进程随便清」。"""
    audio_guard.allow(1)
    _section(db).audio_key = None
    db.commit()
    art = db.query(Artist).filter_by(qid="Q34618").one()
    art.bio_audio = {}
    with pytest.raises(AudioLossBlocked):
        db.commit()


def test_web_record_only_never_blocks_but_still_records(db):
    audio_guard.set_record_only()
    art = db.query(Artist).filter_by(qid="Q34618").one()
    art.bio_audio = {}
    db.commit()
    rows = db.query(AudioInvalidation).all()
    assert {r.language for r in rows} == {"en", "zh"}
    assert all(r.allowed == "record_only" and r.old_text for r in rows)


def test_replacing_a_key_is_an_upgrade_not_a_loss(db):
    """tts-1 → VoxCPM2 重录:换成新 key 不算损失,音频灌入不能被这道闸挡住。"""
    _section(db).audio_key = "object-audio/Q1/zh-guide-v2.mp3"
    art = db.query(Artist).filter_by(qid="Q34618").one()
    art.bio_audio = {**art.bio_audio, "zh": "object-audio/artist/Q34618/zh-v2.mp3"}
    db.commit()
    assert db.query(AudioInvalidation).count() == 0


def test_normal_writes_without_audio_are_untouched(db):
    """无音频行的改写(补语种、翻译落库)不受影响。"""
    from app.services.content_repo import persist_generated_sections

    persist_generated_sections(db, "Q1", "fr", {"guide": "Texte."})
    persist_generated_sections(db, "Q1", "fr", {"guide": "Texte v2."})
    art = db.query(Artist).filter_by(qid="Q34618").one()
    art.bio = {**art.bio, "fr": "Bio fr."}
    db.commit()
    assert db.query(AudioInvalidation).count() == 0
