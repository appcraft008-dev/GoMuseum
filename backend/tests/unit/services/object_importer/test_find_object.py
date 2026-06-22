from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import find_object, upsert_museum, upsert_object


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    return sessionmaker(bind=engine)()


def test_find_object_by_qid_and_inventory():
    s = _session()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "inventory_number": "RF 1", "title_en": "A"})
    s.commit()
    assert find_object(s, m.id, {"qid": "Q1"}).title_en == "A"
    assert find_object(s, m.id, {"inventory_number": "RF 1"}).qid == "Q1"
    assert find_object(s, m.id, {"qid": "Q404"}) is None
