"""物化器:下载→两档(thumb480/large1600 JPEG q82)→R2→署名→image_key(基础键)。
网络/存储全注入离线测。spec 2026-07-03 图像自存。"""

import io

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.materializer import (
    image_base_key,
    materialize_images,
    materialize_object_images,
)
from app.services.object_importer import upsert_museum, upsert_object


def _jpeg_bytes(w=64, h=48):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()


class _Storage:
    def __init__(self):
        self.puts = {}

    def put(self, key, data, content_type):
        self.puts[key] = (data, content_type)

    def public_url(self, key):
        return f"https://cdn.example/{key}"


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
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "A",
            "popularity": 9,
            "images": ["https://img/a.jpg", "https://img/b.jpg"],
        },
    )
    upsert_object(
        s,
        m.id,
        {"qid": "Q2", "title_en": "B", "popularity": 5, "image": "https://img/c.jpg"},
    )
    s.commit()
    yield s


def test_image_base_key():
    assert image_base_key("Q1", 0) == "images/Q1/0"


def test_materialize_object_images_two_tiers_and_credit(session):
    st = _Storage()
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    out = materialize_object_images(
        session,
        o,
        fetch_bytes=lambda url: _jpeg_bytes(2000, 1500),
        storage=st,
        fetch_meta=lambda url: {"license": "CC BY-SA 4.0", "credit": "Photo: X"},
    )
    assert out["done"] == 2
    rows = (
        session.query(ObjectImage)
        .filter_by(object_id=o.id)
        .order_by(ObjectImage.sort)
        .all()
    )
    assert rows[0].image_key == "images/Q1/0"
    assert rows[1].image_key == "images/Q1/1"
    assert rows[0].license == "CC BY-SA 4.0" and rows[0].credit == "Photo: X"
    assert set(st.puts) == {
        "images/Q1/0_thumb.jpg",
        "images/Q1/0_large.jpg",
        "images/Q1/1_thumb.jpg",
        "images/Q1/1_large.jpg",
    }
    thumb = Image.open(io.BytesIO(st.puts["images/Q1/0_thumb.jpg"][0]))
    large = Image.open(io.BytesIO(st.puts["images/Q1/0_large.jpg"][0]))
    assert max(thumb.size) <= 480 and max(large.size) <= 1600
    assert st.puts["images/Q1/0_thumb.jpg"][1] == "image/jpeg"


def test_materialize_failure_leaves_key_empty(session):
    def boom(url):
        raise RuntimeError("network down")

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    out = materialize_object_images(
        session, o, fetch_bytes=boom, storage=_Storage(), fetch_meta=lambda u: {}
    )
    assert out["failed"] == 2 and out["done"] == 0
    assert all(
        r.image_key is None
        for r in session.query(ObjectImage).filter_by(object_id=o.id)
    )


def test_materialize_unreadable_image_skipped(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    out = materialize_object_images(
        session,
        o,
        fetch_bytes=lambda url: b"<svg>not a bitmap</svg>",
        storage=_Storage(),
        fetch_meta=lambda u: {},
    )
    assert out["skipped"] == 2 and out["done"] == 0


def test_materialize_images_museum_wide_idempotent(session):
    st = _Storage()
    kw = dict(
        fetch_bytes=lambda url: _jpeg_bytes(),
        storage=st,
        fetch_meta=lambda url: {},
    )
    out = materialize_images(session, "orsay", **kw)
    assert out["done"] == 3  # Q1×2 + Q2×1
    out2 = materialize_images(session, "orsay", **kw)
    assert out2["done"] == 0  # 已有 key 跳过(幂等)


def test_materialize_images_unknown_museum(session):
    assert materialize_images(
        session, "nope", fetch_bytes=lambda u: b"", storage=_Storage()
    ) == {"error": "unknown museum"}
