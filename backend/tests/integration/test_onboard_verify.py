"""上新馆验收闸:每项检查都要能真的红,否则闸是摆设。
用例逐条对应卢浮宫暴露的六类事故(2026-07-26)。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from scripts.onboard_verify import build_checks

LANGS = ["en", "zh"]


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    upsert_museum(s, {"slug": "m1", "name_en": "M1", "qid": "Q1"})
    s.commit()
    yield s


def _by_name(res, key):
    return next(c for c in res["checks"] if key in c["name"])


def _healthy(s, n=4):
    """造一个各项都达标的馆:译名齐、作者本地化、图物化完、介绍封面齐。"""
    m = s.query(Museum).one()
    m.description_i18n = {"en": "Para one.\n\nPara two.", "zh": "一\n\n二"}
    m.cover_image_key = "images/Q1/0"
    s.add(Artist(qid="Q42", name_en="Rembrandt", name_i18n={"zh": "伦勃朗"}))
    for i in range(n):
        o = upsert_object(
            s, m.id, {"qid": f"Q{100 + i}", "title_en": f"W{i}", "attributes": {}}
        )
        o.artist_en = "Rembrandt"
        o.attributes = {
            "title_i18n": {"en": f"W{i}", "zh": f"作品{i}"},
            "artist_qid": "Q42",
        }
        s.add(
            ObjectImage(
                object_id=o.id,
                role="primary",
                source_url="u",
                image_key=f"images/Q{100 + i}/0",
            )
        )
    s.commit()
    return m


def test_healthy_museum_passes_all(session):
    _healthy(session)
    res = build_checks(session, "m1", LANGS)
    assert res["passed"], [c for c in res["checks"] if not c["ok"]]


def test_empty_catalog_fails(session):
    res = build_checks(session, "m1", LANGS)
    assert not res["passed"] and not _by_name(res, "目录非空")["ok"]


def test_missing_translations_fail(session):
    # 事故①:names 漏跑/半途崩 → 列表大面积外文
    m = _healthy(session)
    for o in session.query(MuseumObject).filter_by(museum_id=m.id).limit(3):
        o.attributes = {**o.attributes, "title_i18n": {"en": "W"}}  # 抽掉 zh
    session.commit()
    res = build_checks(session, "m1", LANGS)
    assert not _by_name(res, "各语言译名覆盖")["ok"]
    assert "names" in _by_name(res, "各语言译名覆盖")["fix"]


def test_missing_english_title_fails(session):
    # 事故②:title_en 只读列的对称性缺失 → 英文用户看到空白
    m = _healthy(session)
    for o in session.query(MuseumObject).filter_by(museum_id=m.id).limit(2):
        o.title_en = None
        o.attributes = {**o.attributes, "title_i18n": {"zh": "作品"}}
    session.commit()
    res = build_checks(session, "m1", LANGS)
    assert not _by_name(res, "英文标题空值")["ok"]


def test_unlocalized_artist_fails(session):
    # 事故③:batch 路径漏 P170 / 馆包读裸列 → 作者名全拉丁
    _healthy(session)
    art = session.query(Artist).filter_by(qid="Q42").one()
    art.name_i18n = {}  # 只有拉丁名,无中文
    session.commit()
    res = build_checks(session, "m1", LANGS)
    assert not _by_name(res, "作者中文名")["ok"]


def test_blank_node_artist_qid_fails(session):
    # 事故④:Wikidata blank node genid 哈希被当成作者身份
    m = _healthy(session)
    o = session.query(MuseumObject).filter_by(museum_id=m.id).first()
    o.attributes = {**o.attributes, "artist_qid": "be8e7c9dfff6275cf709bc59fba78ed0"}
    session.commit()
    res = build_checks(session, "m1", LANGS)
    c = _by_name(res, "artist_qid 格式")
    assert not c["ok"] and "clean_blank_node_artists" in c["fix"]


def test_pending_images_fail(session):
    # 事故⑤:credit 超列宽崩掉整轮物化 → 大量图行留空
    m = _healthy(session)
    o = session.query(MuseumObject).filter_by(museum_id=m.id).first()
    session.add(ObjectImage(object_id=o.id, role="view", source_url="u2"))
    session.commit()
    res = build_checks(session, "m1", LANGS)
    assert not _by_name(res, "图物化无残留")["ok"]


def test_missing_intro_and_cover_fail(session):
    # 事故⑥:配方最后一步漏跑
    m = _healthy(session)
    m.description_i18n = {}
    m.cover_image_key = None
    session.commit()
    res = build_checks(session, "m1", LANGS)
    assert not _by_name(res, "馆介绍")["ok"]
    assert not _by_name(res, "封面已选")["ok"]


def test_unknown_museum_fails(session):
    res = build_checks(session, "nope", LANGS)
    assert not res["passed"]


def test_langs_from_museum_config_not_slug_chars(monkeypatch, capsys):
    """回归:cmd_verify 曾把 slug 传进 resolve_languages → list("louvre") 逐字符
    当语言,每项都 0%、三馆全红(prod 实跑才发现)。语言集必须与 names 同源。"""
    import scripts.onboard as ob

    seen = {}

    def _fake_build(db, slug, langs):
        seen["langs"] = langs
        return {"slug": slug, "checks": [], "passed": True}

    class _Cfg:
        languages = []

    monkeypatch.setattr(
        ob, "_catalog", lambda: type("C", (), {"get": lambda s, x: _Cfg()})()
    )
    monkeypatch.setattr(
        ob, "SessionLocal", lambda: type("S", (), {"close": lambda s: None})()
    )
    monkeypatch.setattr("scripts.onboard_verify.build_checks", _fake_build)
    monkeypatch.setattr(ob.settings, "ENVIRONMENT", "production")
    ob.cmd_verify("louvre", None, "prod", False)

    assert "l" not in seen["langs"], f"逐字符了: {seen['langs']}"
    assert "en" in seen["langs"] and len(seen["langs"]) > 1
