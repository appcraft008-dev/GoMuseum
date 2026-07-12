"""vet_views 三段策略:sim<0.25 删 image+embedding;0.25≤sim<0.4 隔离(role=view_quarantine
+删向量);≥0.4 保留。dry_run 只报数不改动。"""

import math

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.object_importer import upsert_museum, upsert_object
from app.services.recognition.embedder import MODEL_NAME
from scripts.vet_view_images import vet_views


def _unit(cos: float) -> bytes:
    """2D 单位向量,与 [1,0] 的余弦 = cos。"""
    v = np.array([cos, math.sqrt(1 - cos * cos)], dtype=np.float32)
    return v.tobytes()


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

    def add_img(role, sort, cos):
        img = ObjectImage(
            object_id=o.id,
            role=role,
            source_url=f"http://x/{role}{sort}.jpg",
            sort=sort,
        )
        s.add(img)
        s.flush()
        s.add(
            ObjectEmbedding(
                object_id=o.id, image_id=img.id, model=MODEL_NAME, vec=_unit(cos)
            )
        )
        return img

    primary = add_img("primary", 0, 1.0)
    view_high = add_img("view", 0, 0.9)
    view_mid = add_img("view", 1, 0.32)
    view_low = add_img("view", 2, 0.1)
    s.commit()
    return s, o, primary, view_high, view_mid, view_low


def test_three_band_policy(session):
    s, o, primary, view_high, view_mid, view_low = session
    res = vet_views(s, delete_below=0.25, quarantine_below=0.4, dry_run=False)
    assert res == {"checked": 3, "deleted": 1, "quarantined": 1}
    # sim 0.1 → image + embedding 都删
    assert s.query(ObjectImage).filter_by(id=view_low.id).first() is None
    assert s.query(ObjectEmbedding).filter_by(image_id=view_low.id).first() is None
    # sim 0.32 → 隔离:行还在但 role 变 view_quarantine,向量删除(出索引)
    mid = s.query(ObjectImage).filter_by(id=view_mid.id).first()
    assert mid is not None and mid.role == "view_quarantine"
    assert s.query(ObjectEmbedding).filter_by(image_id=view_mid.id).first() is None
    # sim 0.9 → 原样保留
    high = s.query(ObjectImage).filter_by(id=view_high.id).first()
    assert high is not None and high.role == "view"
    assert s.query(ObjectEmbedding).filter_by(image_id=view_high.id).first() is not None
    # primary 不动
    assert s.query(ObjectImage).filter_by(id=primary.id).first() is not None
    assert s.query(ObjectEmbedding).filter_by(image_id=primary.id).first() is not None


def test_dry_run_mutates_nothing(session):
    s, o, primary, view_high, view_mid, view_low = session
    res = vet_views(s, delete_below=0.25, quarantine_below=0.4, dry_run=True)
    assert res == {"checked": 3, "deleted": 1, "quarantined": 1}
    assert s.query(ObjectImage).count() == 4
    assert s.query(ObjectEmbedding).count() == 4
    assert {i.role for i in s.query(ObjectImage).all()} == {"primary", "view"}
