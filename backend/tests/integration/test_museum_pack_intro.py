"""馆包 description(按语言解析+回退)与 cover_image(large 直链)——全 null 安全。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services import museum_repo
from app.services.object_importer import upsert_museum


@pytest.fixture()
def session(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    s.commit()

    class _Storage:
        def public_url(self, key):
            return f"https://r2/{key}"

    monkeypatch.setattr(museum_repo, "get_object_storage", lambda: _Storage())
    yield s


def test_pack_description_resolves_language_with_fallback(session):
    m = session.query(Museum).one()
    m.description_i18n = {"en": "EN intro.", "zh": "中文介绍。"}
    session.commit()
    assert (
        museum_repo.get_museum_pack(session, "orsay", "zh")["description"]
        == "中文介绍。"
    )
    assert (
        museum_repo.get_museum_pack(session, "orsay", "ja")["description"]
        == "EN intro."
    )  # 缺→en


def test_pack_description_and_cover_null_safe(session):
    pack = museum_repo.get_museum_pack(session, "orsay", "zh")
    assert pack["description"] is None
    assert pack["cover_image"] is None


def test_pack_cover_image_large_url(session):
    m = session.query(Museum).one()
    m.cover_image_key = "images/Q1/0"
    session.commit()
    pack = museum_repo.get_museum_pack(session, "orsay", "zh")
    assert pack["cover_image"] == "https://r2/images/Q1/0_large.jpg"
