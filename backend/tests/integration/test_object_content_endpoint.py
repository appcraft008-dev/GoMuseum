# tests/integration/test_object_content_endpoint.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
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
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    obj = upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "A",
            "category": "painting",
            "image": "http://x/a.jpg",
            "attributes": {},
        },
    )
    # A second museum for slug-mismatch test
    m2 = upsert_museum(s, {"slug": "louvre", "name_en": "Louvre"})
    s.add(
        SectionType(
            code="overview", label_zh="通用描述", label_en="Overview", default_sort=10
        )
    )
    s.add(CategorySection(category="painting", section_code="overview", sort_order=10))
    s.add(
        ObjectContentSection(
            object_id=obj.id, language="zh", section_code="overview", body="讲解正文"
        )
    )
    # fr 也给已发布正文,否则无正文的 tab 现在会被动态隐藏(空 tab 不返)
    s.add(
        ObjectContentSection(
            object_id=obj.id, language="fr", section_code="overview", body="texte fr"
        )
    )
    s.commit()
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    s.close()


def test_object_content_tabs(client):
    r = client.get("/api/v1/museums/orsay/objects/Q1/content?language=zh")
    assert r.status_code == 200
    tabs = r.json()["tabs"]
    assert tabs[0]["section_code"] == "overview"
    assert tabs[0]["label"] == "通用描述"
    assert tabs[0]["body"] == "讲解正文"


def test_object_content_not_found(client):
    """Non-existent qid returns 404."""
    r = client.get("/api/v1/museums/orsay/objects/QNOPE/content")
    assert r.status_code == 404


def test_object_content_slug_mismatch(client):
    """Object exists but under a different museum slug → 404."""
    r = client.get("/api/v1/museums/louvre/objects/Q1/content?language=zh")
    assert r.status_code == 404


def test_object_content_labels_localized_fr(client):
    r = client.get("/api/v1/museums/orsay/objects/Q1/content?language=fr")
    assert r.status_code == 200
    tabs = r.json()["tabs"]
    overview = next((t for t in tabs if t["section_code"] == "overview"), None)
    assert overview is not None
    assert overview["label"] == "Aperçu"
