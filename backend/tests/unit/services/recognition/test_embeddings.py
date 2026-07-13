"""embed_image_row:入库即嵌入(幂等/None不回退/坏字节不炸)+ view 入库闸三段。"""

import io
import math

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
from app.services.recognition.embedder import MODEL_NAME
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


# ---- view 入库闸:primary 已有向量时,新 view 先算 sim 再决定 删/隔离/正常嵌入 ----


def _unit_vec(cos: float) -> np.ndarray:
    """2D 单位向量,与 [1,0] 的余弦 = cos。"""
    return np.array([cos, math.sqrt(1 - cos * cos)], dtype=np.float32)


def _fake(cos: float):
    return type("E", (), {"embed": lambda self, im: _unit_vec(cos)})()


def _add_primary_embedding(s, o, img):
    s.add(
        ObjectEmbedding(
            object_id=o.id,
            image_id=img.id,
            model=MODEL_NAME,
            vec=_unit_vec(1.0).tobytes(),
        )
    )
    s.commit()


def _add_view(s, o):
    view = ObjectImage(object_id=o.id, role="view", source_url="http://x/v.jpg", sort=1)
    s.add(view)
    s.commit()
    return view


def test_view_gate_low_sim_deletes_row(session):
    s, o, img = session
    _add_primary_embedding(s, o, img)
    view = _add_view(s, o)
    assert embed_image_row(s, view, _tiny_png_bytes(), embedder=_fake(0.1)) is False
    s.commit()
    assert s.query(ObjectImage).filter_by(id=view.id).first() is None
    assert s.query(ObjectEmbedding).filter_by(image_id=view.id).first() is None


def test_view_gate_mid_sim_quarantines(session):
    s, o, img = session
    _add_primary_embedding(s, o, img)
    view = _add_view(s, o)
    assert embed_image_row(s, view, _tiny_png_bytes(), embedder=_fake(0.32)) is False
    s.commit()
    row = s.query(ObjectImage).filter_by(id=view.id).first()
    assert row is not None and row.role == "view_quarantine"
    assert s.query(ObjectEmbedding).filter_by(image_id=view.id).first() is None


def test_view_gate_high_sim_embeds(session):
    s, o, img = session
    _add_primary_embedding(s, o, img)
    view = _add_view(s, o)
    assert embed_image_row(s, view, _tiny_png_bytes(), embedder=_fake(0.9)) is True
    s.commit()
    assert s.query(ObjectImage).filter_by(id=view.id).first().role == "view"
    assert s.query(ObjectEmbedding).filter_by(image_id=view.id).first() is not None


def test_view_gate_no_primary_embedding_embeds_normally(session):
    s, o, img = session  # primary 图存在但无向量 → 闸不启动,照常嵌入
    view = _add_view(s, o)
    assert embed_image_row(s, view, _tiny_png_bytes(), embedder=_fake(0.1)) is True
    s.commit()
    assert s.query(ObjectEmbedding).filter_by(image_id=view.id).first() is not None
