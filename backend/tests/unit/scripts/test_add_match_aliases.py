"""英文匹配别名一次性脚本:只写 attributes.match_aliases;dry-run 不写;同形不写;幂等;备份写入面。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from scripts.add_match_aliases import run, targets, translate_batch


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    s.commit()
    return s


def _add(db, qid, en, fr, aliases=None):
    m = db.query(Museum).filter_by(slug="orsay").one()
    attrs = {"title_i18n": {"en": en, "fr": fr}}
    if aliases:
        attrs["match_aliases"] = aliases
    upsert_object(
        db,
        m.id,
        {"qid": qid, "title_en": en, "category": "painting", "attributes": attrs},
    )
    db.commit()


def fake_complete(system, user):
    titles = json.loads(user)
    table = {"L'Air du soir": "The Evening Air", "Sarah Bernhardt": "Sarah Bernhardt"}
    return json.dumps([table.get(t) for t in titles])


def _attrs(db, qid):
    return db.query(MuseumObject).filter_by(qid=qid).one().attributes


def test_targets_only_french_as_english(db):
    _add(db, "Q1", "L'air du soir", "L'Air du soir")
    _add(db, "Q2", "Luncheon on the Grass", "Le Déjeuner sur l'herbe")
    _add(db, "Q3", "L'air du soir", "L'Air du soir", aliases=["x"])  # 已有 → 跳过
    assert [o.qid for o in targets(db)] == ["Q1"]


def test_translate_batch_shape():
    assert translate_batch(["L'Air du soir"], fake_complete) == ["The Evening Air"]
    assert translate_batch(["a", "b"], lambda s, u: "[]") == [None, None]  # 长度不符
    assert translate_batch(["a"], lambda s, u: "not json") == [None]


def test_dry_run_writes_nothing(db):
    _add(db, "Q1", "L'air du soir", "L'Air du soir")
    rep = run(db, fake_complete, apply=False, backup=None)
    assert rep["targets"] == 1 and rep["written"] == 0
    assert "match_aliases" not in _attrs(db, "Q1")


def test_apply_writes_alias_and_skips_same_form(db, tmp_path):
    _add(db, "Q1", "L'air du soir", "L'Air du soir")
    _add(db, "Q4", "Sarah Bernhardt", "Sarah Bernhardt")
    bk = tmp_path / "bk.json"
    rep = run(db, fake_complete, apply=True, backup=str(bk))
    assert _attrs(db, "Q1")["match_aliases"] == ["The Evening Air"]
    assert _attrs(db, "Q1")["title_i18n"] == {
        "en": "L'air du soir",
        "fr": "L'Air du soir",
    }
    assert rep["same_as_source"] == 1  # 译文与原文同形 → 不写
    assert "match_aliases" not in _attrs(db, "Q4")
    saved = json.loads(bk.read_text())
    assert {r["qid"] for r in saved} == {"Q1", "Q4"}  # 备份=写入面全部行的原 attributes


def test_apply_is_idempotent(db):
    _add(db, "Q1", "L'air du soir", "L'Air du soir")
    run(db, fake_complete, apply=True, backup=None)
    assert run(db, fake_complete, apply=True, backup=None)["targets"] == 0
