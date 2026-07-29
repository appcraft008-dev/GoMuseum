"""音频队列的分层规则 + 替换质量闸。

写错的代价:分层错 → 白烧几十天 GPU;质量闸松 → 模型回归静默毁掉音频库
(旧文件已被替换成孤儿,不可逆)。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
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


def test_facts_never_enters_the_queue(db):
    """facts 是列表展示不是叙述文本(前端 factsExpanded 开关),排进去纯属白烧。"""
    s, m = db
    o = _obj(s, m, "Q1")
    _sec(s, o, "facts")
    jobs = aq.build_queue(s, languages=["zh"], target_engine="voxcpm2")
    assert all(j.section != "facts" for j in jobs)


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
