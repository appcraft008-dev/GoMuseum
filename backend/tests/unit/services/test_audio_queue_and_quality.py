"""音频队列的分层规则 + 替换质量闸。

写错的代价:分层错 → 白烧几十天 GPU;质量闸松 → 模型回归静默毁掉音频库
(旧文件已被替换成孤儿,不可逆)。
"""

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
from app.services.enrichment import audio_queue as aq
from app.services.enrichment.audio_quality import check_audio, estimate_duration_sec


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
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=e)()
    m = Museum(slug="louvre", name_en="Louvre", city_en="Paris")
    s.add(m)
    s.commit()
    yield s, m
    s.close()


def _obj(s, m, qid):
    o = MuseumObject(museum_id=m.id, qid=qid)
    s.add(o)
    s.commit()
    return o


def _sec(s, o, code, lang="zh", body="正文" * 100, key=None, engine=None):
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language=lang,
            section_code=code,
            body=body,
            audio_key=key,
            audio_engine=engine,
        )
    )
    s.commit()


def test_hero_missing_is_top_priority(db):
    """主讲解缺音频最急 —— 它是识别成功后**自动播**的,卡 5 秒直接伤转化。"""
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide")
    _sec(s, o, "background")

    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2")
    hero = [j for j in jobs if j.section == "guide"][0]
    others = [j for j in jobs if j.section != "guide"]
    assert hero.reason == "hero_missing"
    assert all(hero.priority < o2.priority for o2 in others), "guide 必须排在最前"


def test_long_tail_gets_hero_only(db):
    """长尾件只做主讲解:深度段几乎没人点,预生成是白烧 GPU。"""
    s, m = db
    for i in range(3):
        o = _obj(s, m, f"Q{i}")
        _sec(s, o, "guide")
        _sec(s, o, "background")
        _sec(s, o, "analysis")

    # head_size=1 → 只有第一件算头部
    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2", head_size=1)
    tail = [j for j in jobs if j.qid in ("Q1", "Q2")]
    assert tail, "长尾件也该有任务"
    assert {j.section for j in tail} == {"guide"}, "长尾件只做 guide"

    head = [j for j in jobs if j.qid == "Q0"]
    assert len({j.section for j in head}) > 1, "头部件应全段"


def test_facts_is_narrated_not_excluded(db):
    """facts 是**轶事叙述**,该念。

    曾从前端组件名(factsExpanded)推断它是元数据列表而排除 —— 实际正文是
    "……曾被藏在古董店木板后面,直到 1889 年被贡库尔发现",119 字 ≈ 25 秒。
    教训:别凭组件名推断内容性质,去看正文。
    """
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide")
    _sec(s, o, "facts")
    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2", head_size=10)
    assert any(j.section == "facts" for j in jobs), "轶事段该进队列"


def test_already_target_engine_is_skipped(db):
    """已经是目标引擎的不重做 —— 否则每天扫描都在重复生成。"""
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide", key="k", engine="voxcpm2")
    assert aq.build_queue(s, languages=["zh"], target_engine="voxcpm2") == []


def test_upgrades_can_be_turned_off(db):
    """冷启动阶段应先只补缺失:音色升级排在后面,别和补缺抢 GPU。"""
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide", key="k", engine="tts-1")

    assert aq.build_queue(s, languages=["zh"], target_engine="voxcpm2") != []
    assert (
        aq.build_queue(
            s, languages=["zh"], target_engine="voxcpm2", include_upgrades=False
        )
        == []
    )


def test_language_filter_respects_quality_gate_rollout(db):
    """按语言分批启用:VoxCPM2 欧语未达标前,不该把 en/fr 排进队列。"""
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide", lang="zh")
    _sec(s, o, "guide", lang="fr")
    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2")
    assert {j.language for j in jobs} == {"zh"}


# ── 质量闸 ────────────────────────────────────────────────────────────────


def _bytes_for(seconds: float) -> bytes:
    return b"\0" * int(seconds * 160_000 / 8)


def test_truncated_audio_is_rejected():
    """最常见的真实故障:生成中途截断。"""
    text = "字" * 280  # zh 约 280 字/分钟 → 期望 60 秒
    v = check_audio(_bytes_for(15), text=text, language="zh")
    assert v.ok is False and "too_short" in v.reason


def test_runaway_repetition_is_rejected():
    text = "字" * 280
    v = check_audio(_bytes_for(200), text=text, language="zh")
    assert v.ok is False and "too_long" in v.reason


def test_reasonable_audio_passes():
    text = "字" * 280
    v = check_audio(_bytes_for(58), text=text, language="zh")
    assert v.ok is True, v.reason


def test_replacement_must_not_deviate_wildly():
    """⭐ 替换场景最有用的一条:同一段文本换引擎,时长差一倍必有问题。
    不过闸就保留旧版本 —— 模型回归不该静默毁掉音频库。"""
    text = "字" * 280
    ok = check_audio(_bytes_for(58), text=text, language="zh", previous_duration_sec=60)
    assert ok.ok is True
    bad = check_audio(
        _bytes_for(58), text=text, language="zh", previous_duration_sec=20
    )
    assert bad.ok is False and "deviates" in bad.reason


def test_empty_audio_is_rejected():
    assert check_audio(b"", text="字" * 100, language="zh").ok is False


def test_duration_estimate_matches_bitrate():
    assert abs(estimate_duration_sec(_bytes_for(30)) - 30) < 0.1


# —— 作者介绍:第三处存音频 key 的地方(2026-07-30 补) ——


def _artist(s, o, aqid, bio=None, key=None, engine=None):
    """建作者并挂到作品上(bio 音频按作者共享,key 走 artist qid)。"""
    s.add(
        Artist(
            qid=aqid,
            bio=bio or {"zh": "作者生平" * 50},
            bio_audio={"zh": key} if key else None,
            bio_audio_engine={"zh": engine} if engine else None,
        )
    )
    o.attributes = {**(o.attributes or {}), "artist_qid": aqid}
    s.commit()


def test_artist_bio_enters_the_migration_queue(db):
    """作者介绍必须进队列。

    漏掉它 = 迁移完"作品讲解是新音色、点作者介绍变回旧音色",而 audio_queue
    自己的目标就是"一次参观内部音色一致"。bio 还是按作者共享的,一条音频在
    该作者所有作品下播放,影响面要乘以作品数。
    """
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide")
    _artist(s, o, "Q5582")

    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2")
    bio_jobs = [j for j in jobs if j.kind == "artist_bio"]
    assert len(bio_jobs) == 1
    assert bio_jobs[0].qid == "Q5582", "按作者 qid 排,不是作品 qid"
    assert bio_jobs[0].section == "artist_bio"


def test_artist_bio_already_on_target_engine_is_skipped(db):
    """已经是目标引擎的不重做 —— 否则每次跑队列都白烧一遍 GPU。"""
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide")
    _artist(s, o, "Q5582", key="k", engine="voxcpm2")

    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2")
    assert [j for j in jobs if j.kind == "artist_bio"] == []


def test_artist_bio_on_old_engine_is_an_upgrade(db):
    """旧引擎生成的 → 排进音色统一批次(这正是当初漏掉的那类)。"""
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide")
    _artist(s, o, "Q5582", key="k", engine="tts-1")

    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2")
    bio = [j for j in jobs if j.kind == "artist_bio"][0]
    assert bio.reason == "engine_upgrade"


def test_shared_artist_is_not_queued_once_per_artwork(db):
    """同一作者的多件作品只排一条 —— 音频按作者共享,排 N 次就是白做 N-1 次。"""
    s, m = db
    for qid in ("Q1", "Q2", "Q3"):
        o = _obj(s, m, qid)
        _sec(s, o, "guide")
        o.attributes = {"artist_qid": "Q5582"}
    s.add(Artist(qid="Q5582", bio={"zh": "作者生平" * 50}))
    s.commit()

    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2")
    assert len([j for j in jobs if j.kind == "artist_bio"]) == 1


def test_coverage_reports_artist_bio_separately(db):
    """报表要单列作者介绍 —— 只报 guide 的话,它看着永远 100%,实际一条没迁。"""
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "guide", key="k1", engine="tts-1")
    _artist(s, o, "Q5582", key="k2", engine="tts-1")

    cov = aq.coverage(s, ["zh"])
    assert cov["guide"]["zh"]["tts-1"] == 1
    assert cov["artist_bio"]["zh"]["tts-1"] == 1
