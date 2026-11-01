"""下架/隔离过的图:catalog 重跑不许把它改回 primary;Wikidata 换了新图才收新图。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object

OLD = "https://commons.wikimedia.org/wiki/Special:FilePath/old.jpg"
NEW = "https://commons.wikimedia.org/wiki/Special:FilePath/new.jpg"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [Museum.__table__, MuseumObject.__table__, ObjectImage.__table__]
    Base.metadata.create_all(engine, tables=tables)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _load(db, url):
    m = upsert_museum(db, {"slug": "m", "qid": "Q1", "name_en": "M"})
    return upsert_object(db, m.id, {"qid": "Q2", "title_en": "T", "images": [url]})


def test_rerun_keeps_quarantined_image_hidden(db):
    o = _load(db, OLD)
    db.query(ObjectImage).filter_by(object_id=o.id).one().role = "view_quarantine"
    _load(db, OLD)
    assert db.query(ObjectImage).filter_by(object_id=o.id).one().role == (
        "view_quarantine"
    )


def test_new_source_image_replaces_quarantined_one(db):
    o = _load(db, OLD)
    row = db.query(ObjectImage).filter_by(object_id=o.id).one()
    row.role, row.image_key = "view_quarantine", "images/Q2/0"
    _load(db, NEW)
    assert (row.role, row.source_url, row.image_key) == ("primary", NEW, None)
