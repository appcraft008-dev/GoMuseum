import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import museums
from app.core.database import Base, get_db
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def client():
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
    TestingSession = sessionmaker(bind=engine)
    s = TestingSession()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "A",
            "category": "painting",
            "popularity": 9,
            "image": "http://i/1.jpg",  # 有图过滤后:列表对象需有图
        },
    )
    s.commit()
    s.close()

    app = FastAPI()
    app.include_router(museums.router, prefix="/museums")
    app.dependency_overrides[get_db] = lambda: TestingSession()
    return TestClient(app)


def test_objects_endpoint_returns_page(client):
    r = client.get("/museums/orsay/objects", params={"limit": 10, "offset": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["limit"] == 10
    assert body["items"][0]["qid"] == "Q1"
    assert "content_status" in body["items"][0]


def test_objects_endpoint_unknown_museum_404(client):
    assert client.get("/museums/nope/objects").status_code == 404


def test_list_order_matches_top_objects_on_popularity_ties(client):
    """同分必须有确定顺序且与生成用的 top_objects 一致:否则 App 列表前 N 件
    ≠ 已生成的 TOP-N(小皇宫第 19 位显示「待完善」),分页也会重复/漏件。"""
    from app.services.enrichment.pipeline import top_objects

    s = client.app.dependency_overrides[get_db]()
    m = s.query(Museum).filter_by(slug="orsay").one()
    for i in range(8):
        upsert_object(
            s,
            m.id,
            {
                "qid": f"Q{100 + i}",
                "title_en": "T",
                "popularity": 4,
                "image": f"http://i/{i}.jpg",
            },
        )
    s.commit()
    expected = [o.qid for o in top_objects(s, m.id).all()]
    s.close()

    pages = [
        client.get("/museums/orsay/objects", params={"limit": 3, "offset": off}).json()[
            "items"
        ]
        for off in (0, 3, 6)
    ]
    assert [it["qid"] for p in pages for it in p] == expected
