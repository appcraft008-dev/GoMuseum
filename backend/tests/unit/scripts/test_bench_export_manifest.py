"""manifest 导出:只含有图有qid的件;storage 不可用时回退 source_url。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from scripts.recognition_bench.export_manifest import export_manifest


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
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o1 = upsert_object(
        s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting", "popularity": 9}
    )
    o2 = upsert_object(
        s,
        m.id,
        {"qid": "Q2", "title_en": "B", "category": "sculpture", "popularity": 5},
    )
    upsert_object(s, m.id, {"qid": "Q3", "title_en": "no-image", "popularity": 1})
    s.add(ObjectImage(object_id=o1.id, source_url="http://x/1.jpg", sort=0))
    s.add(ObjectImage(object_id=o1.id, source_url="http://x/2.jpg", sort=1))
    s.add(ObjectImage(object_id=o2.id, source_url="http://x/3.jpg", sort=0))
    s.commit()
    return s


def test_manifest_shape_and_filtering(session):
    m = export_manifest(session, "orsay")
    assert m["museum"] == "orsay"
    qids = [o["qid"] for o in m["objects"]]
    assert qids == ["Q1", "Q2"]  # popularity 降序;Q3 无图被滤掉
    assert m["objects"][0]["images"] == ["http://x/1.jpg", "http://x/2.jpg"]
    assert m["objects"][1]["category"] == "sculpture"
