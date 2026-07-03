"""多角度图入库:art["images"] 列表 → 多行 ObjectImage(primary/view,sort=序号)。幂等。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    yield s


def _rows(s, obj):
    return (
        s.query(ObjectImage)
        .filter_by(object_id=obj.id)
        .order_by(ObjectImage.sort)
        .all()
    )


def test_upsert_object_multi_images(session):
    m = upsert_museum(session, {"slug": "orsay", "name_en": "Orsay"})
    obj = upsert_object(
        session,
        m.id,
        {
            "qid": "Q1",
            "title_en": "A",
            "images": ["http://img/a.jpg", "http://img/b.jpg"],
        },
    )
    rows = _rows(session, obj)
    assert [(r.role, r.sort) for r in rows] == [("primary", 0), ("view", 1)]
    assert rows[0].source_url == "https://img/a.jpg"  # http→https
    # 幂等:重跑不翻倍
    upsert_object(
        session,
        m.id,
        {"qid": "Q1", "images": ["http://img/a.jpg", "http://img/b.jpg"]},
    )
    assert len(_rows(session, obj)) == 2


def test_upsert_object_single_image_backcompat(session):
    m = upsert_museum(session, {"slug": "orsay", "name_en": "Orsay"})
    obj = upsert_object(
        session, m.id, {"qid": "Q2", "title_en": "B", "image": "http://img/x.jpg"}
    )
    rows = _rows(session, obj)
    assert len(rows) == 1 and rows[0].role == "primary"
