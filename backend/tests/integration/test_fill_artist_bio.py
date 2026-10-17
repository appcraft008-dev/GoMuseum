"""作者 bio 补缺(纪律 37:共享实体只补缺)。补语言阶段要在主线程单独调它,
线程里的 translate_object_language 传 include_bio=False 不碰 artists(spec 2026-10-17 §4.2)。"""

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
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.backfill import (
    fill_artist_bio,
    translate_object_language,
)
from app.services.object_importer import upsert_museum, upsert_object

BIO_EN = "Claude Monet was a French painter and a founder of Impressionism."


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
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {**(o.attributes or {}), "artist_qid": "Q296"}
    s.add(
        Artist(qid="Q296", name_en="Claude Monet", bio={"en": BIO_EN, "fr": "Bio FR."})
    )
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language="en",
            section_code="guide",
            body="EN guide.",
            status="published",
        )
    )
    s.commit()
    yield s


class _Tr:
    def __init__(self):
        self.calls = []

    def translate_object(self, en_sections, target_langs, **_kw):
        from app.services.enrichment.quality import SectionQuality

        lang = target_langs[0]
        return {
            lang: {
                c: SectionQuality(
                    body=f"{lang} {b}",
                    status="published",
                    grounding_ratio=1.0,
                    conflicts=[],
                    score=1.0,
                )
                for c, b in en_sections.items()
            }
        }

    def translate_section(self, text, lang, **_kw):
        self.calls.append((lang, text))
        return f"{lang}:{text}"

    def check_faithfulness(self, en, translated, lang, **_kw):
        return True, []


def _obj(s):
    return s.query(MuseumObject).filter_by(qid="Q1").one()


def _bio(s):
    return s.query(Artist).filter_by(qid="Q296").one().bio


def test_fill_artist_bio_adds_missing_language(session):
    tr = _Tr()
    assert fill_artist_bio(session, _obj(session), "de", tr) == 1
    assert _bio(session)["de"] == f"de:{BIO_EN}"


def test_fill_artist_bio_never_overwrites_existing(session):
    tr = _Tr()
    assert fill_artist_bio(session, _obj(session), "fr", tr) == 0
    assert _bio(session)["fr"] == "Bio FR."
    assert tr.calls == []


def test_fill_artist_bio_refresh_keeps_concurrent_write(session):
    # 另一条会话(同作者另一件的生成)先补了 it;refresh=True 写 de 时不能把 it 覆盖掉
    # 持有引用:作者行留在本会话 identity map 里(否则弱引用被回收、query 本来就重读库,
    # 去掉 refresh 也能过 —— 独立审查实测抓到的假测试)
    held = session.query(Artist).filter_by(qid="Q296").one()
    assert "it" not in held.bio
    other = sessionmaker(bind=session.get_bind())()
    art = other.query(Artist).filter_by(qid="Q296").one()
    art.bio = {**art.bio, "it": "Bio IT."}
    other.commit()
    fill_artist_bio(session, _obj(session), "de", _Tr(), refresh=True)
    session.commit()
    assert set(_bio(session)) == {"en", "fr", "it", "de"}


def test_translate_object_language_include_bio_false_leaves_artist(session):
    out = translate_object_language(
        session, _obj(session), "de", _Tr(), include_bio=False
    )
    assert out["bios"] == 0
    assert "de" not in _bio(session)
    assert out["sections"] == 1  # 段照常翻


def test_translate_object_language_default_still_fills_bio(session):
    out = translate_object_language(session, _obj(session), "de", _Tr())
    assert out["bios"] == 1
    assert _bio(session)["de"] == f"de:{BIO_EN}"
