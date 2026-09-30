"""「」→《》只换本作品标题;繁体正常引号、别的作品、音频一律不动。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.object_importer import upsert_museum, upsert_object
from scripts.fix_zh_title_quotes import apply, plan


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
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o = upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "Ship of Fools",
            "attributes": {"title_i18n": {"zh-hant": "愚人船", "zh": "愚人船"}},
        },
    )
    s.flush()
    s.add_all(
        [
            ObjectContentSection(
                object_id=o.id,
                language="zh-hant",
                section_code="guide",
                status="published",
                audio_key="a.mp3",
                body="觀察「愚人船」。他說「別動」。與布蘭特的《愚人船》呼應。「別的畫」",
            ),
            ObjectContentSection(
                object_id=o.id,
                language="en",
                section_code="guide",
                status="published",
                body="「愚人船」",  # 非中文不在范围
            ),
            ObjectSuggestedQuestion(
                object_id=o.id,
                language="zh",
                sort=0,
                question="「愚人船」讲什么？",
                answer="讲一艘船。",
            ),
        ]
    )
    s.commit()
    yield s


def test_only_own_title_quotes_change_and_audio_is_kept(db, tmp_path):
    items = plan(db)
    assert len(items) == 2
    backup = tmp_path / "b.json"
    apply(db, items, str(backup))

    sec = db.query(ObjectContentSection).filter_by(language="zh-hant").one()
    assert (
        sec.body == "觀察《愚人船》。他說「別動」。與布蘭特的《愚人船》呼應。「別的畫」"
    )
    assert sec.audio_key == "a.mp3"  # 引号不发音,音频不作废
    assert (
        db.query(ObjectContentSection).filter_by(language="en").one().body
        == "「愚人船」"
    )
    assert db.query(ObjectSuggestedQuestion).one().question == "《愚人船》讲什么？"

    saved = json.loads(backup.read_text())
    assert {r["table"] for r in saved} == {
        "object_content_sections",
        "object_suggested_questions",
    }
    assert any("觀察「愚人船」" in (r.get("body") or "") for r in saved)
    assert plan(db) == []  # 幂等
