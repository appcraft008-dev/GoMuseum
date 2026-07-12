"""有图过滤(列表/分类计数)+ 馆页双数字(catalog_count/archive_count)。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services import museum_repo
from app.services.object_importer import upsert_museum, upsert_object


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
            ObjectContentSection.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    # 有图件
    imaged = upsert_object(
        s, m.id, {"qid": "Q1", "title_en": "Imaged", "category": "painting"}
    )
    s.add(ObjectImage(object_id=imaged.id, role="primary", source_url="http://x/1.jpg"))
    # 无图 stub(Task 2 落库,无任何 image 行)
    upsert_object(s, m.id, {"qid": "Q2", "title_en": "Stub", "category": "sculpture"})
    s.commit()
    return s, m


def test_list_objects_excludes_imageless(session):
    s, m = session
    res = museum_repo.list_objects(s, "orsay")
    assert [i["qid"] for i in res["items"]] == ["Q1"]
    assert res["total"] == 1


def test_category_counts_exclude_stub(session):
    s, m = session
    pack = museum_repo.get_museum_pack(s, "orsay")
    counts = {c["code"]: c["count"] for c in pack["categories"]}
    assert counts["all"] == 1
    assert counts.get("painting") == 1
    assert "sculpture" not in counts  # stub 无图 → 该类目计数为 0,不出现


def test_pack_double_numbers_live_compute(session):
    s, m = session
    pack = museum_repo.get_museum_pack(s, "orsay")
    assert pack["catalog_count"] == 1  # 有图件数
    assert pack["archive_count"] == 2  # 总件数


def test_pack_double_numbers_from_stats(session):
    s, m = session
    m.stats = {"catalog_count": 10, "archive_count": 20}
    s.commit()
    pack = museum_repo.get_museum_pack(s, "orsay")
    assert pack["catalog_count"] == 10
    assert pack["archive_count"] == 20


def test_quarantined_only_counts_as_imageless(session):
    s, m = session
    q = upsert_object(
        s, m.id, {"qid": "Q3", "title_en": "Quarantined", "category": "painting"}
    )
    s.add(
        ObjectImage(object_id=q.id, role="view_quarantine", source_url="http://x/q.jpg")
    )
    s.commit()
    res = museum_repo.list_objects(s, "orsay")
    assert [i["qid"] for i in res["items"]] == ["Q1"]  # Q3 隔离图不算有图
    assert res["total"] == 1
