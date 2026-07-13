from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.catalog_loader import load_stubs
from app.services.enrichment.catalog_source import StubRecord


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    return sessionmaker(bind=engine)()


def _stub(qid, title="T", inv=None, raw=None):
    return StubRecord(
        inventory_number=inv,
        qid=qid,
        title=title,
        artist="Manet",
        year="1868",
        category="painting",
        image_url="http://img/x.jpg",
        popularity=5,
        owning_museum="orsay",
        source="wikidata",
        raw=raw or {},
        external_ids={"P347": "j1"},
        wiki_titles={"en": "The_Balcony"},
    )


def _museum():
    return {"slug": "orsay", "name_en": "Orsay", "name_zh": "奥赛"}


def test_load_stubs_creates_stub_objects_with_routing():
    s = _session()
    out = load_stubs(s, _museum(), [_stub("Q1", inv="RF 1")])
    assert out["loaded"] == 1 and out["stub"] == 1
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.content_status == "stub"
    assert o.title_en == "T" and o.popularity == 5
    assert o.attributes["external_ids"] == {"P347": "j1"}
    assert o.attributes["wiki_titles"] == {"en": "The_Balcony"}
    img = s.query(ObjectImage).filter_by(object_id=o.id, role="primary").one()
    assert img.source_url == "https://img/x.jpg"


def test_load_stubs_preserves_ready_status_and_material():
    s = _session()
    load_stubs(s, _museum(), [_stub("Q1")])
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "ready"
    o.attributes = {**o.attributes, "extract_en": "已生成材料"}
    s.commit()
    # 再列一次：不下调 ready，且保留已抓材料
    out = load_stubs(s, _museum(), [_stub("Q1")])
    assert out["stub"] == 0
    o2 = s.query(MuseumObject).filter_by(qid="Q1").one()
    assert o2.content_status == "ready"
    assert o2.attributes["extract_en"] == "已生成材料"
    assert o2.attributes["external_ids"] == {"P347": "j1"}


def test_load_stubs_puts_p276_into_attributes():
    s = _session()
    load_stubs(s, _museum(), [_stub("Q1", inv="RF 1", raw={"p276_qid": "Q123456"})])
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["p276"] == "Q123456"
