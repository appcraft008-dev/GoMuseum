"""embed_image_row:入库即嵌入(幂等/None不回退/坏字节不炸)。"""

import io

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.object_importer import upsert_museum, upsert_object
from app.services.recognition.embeddings import embed_image_row


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
            ObjectEmbedding.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o = upsert_object(s, m.id, {"qid": "Q1", "title_en": "A"})
    img = ObjectImage(object_id=o.id, source_url="http://x/1.jpg", sort=0)
    s.add(img)
    s.commit()
    return s, o, img


def _tiny_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    return buf.getvalue()


def test_embed_image_row_and_idempotent(session):
    s, o, img = session
    fake = type("E", (), {"embed": lambda self, im: np.ones(4, dtype=np.float32)})()
    png = _tiny_png_bytes()
    assert embed_image_row(s, img, png, embedder=fake) is True
    s.commit()
    assert embed_image_row(s, img, png, embedder=fake) is True  # 幂等不重插
    s.commit()
    assert s.query(ObjectEmbedding).count() == 1


def test_no_embedder_returns_false(session):
    s, o, img = session
    assert embed_image_row(s, img, b"whatever", embedder=None) is False


def test_bad_bytes_logged_not_raised(session):
    s, o, img = session
    fake = type("E", (), {"embed": lambda self, im: np.ones(4, dtype=np.float32)})()
    assert embed_image_row(s, img, b"not-an-image", embedder=fake) is False
