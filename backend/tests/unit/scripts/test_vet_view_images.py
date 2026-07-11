"""vet_views:低相似度 view 的 image+embedding 被删,高相似度/primary 不动;dry_run 不删。"""

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
    view_low = add_img("view", 1, 0.1)
    s.commit()
    return s, o, primary, view_high, view_low


def test_low_sim_view_deleted_others_intact(session):
    s, o, primary, view_high, view_low = session
    checked, deleted = vet_views(s, min_sim=0.4, dry_run=False)
    assert (checked, deleted) == (2, 1)
    # 低相似 view 的 image + embedding 都没了
    assert s.query(ObjectImage).filter_by(id=view_low.id).first() is None
    assert s.query(ObjectEmbedding).filter_by(image_id=view_low.id).first() is None
    # 高相似 view 与 primary 都在
    assert s.query(ObjectImage).filter_by(id=view_high.id).first() is not None
    assert s.query(ObjectImage).filter_by(id=primary.id).first() is not None
    assert s.query(ObjectEmbedding).filter_by(image_id=primary.id).first() is not None


def test_dry_run_deletes_nothing(session):
    s, o, primary, view_high, view_low = session
    checked, deleted = vet_views(s, min_sim=0.4, dry_run=True)
    assert checked == 2
    assert s.query(ObjectImage).count() == 3
    assert s.query(ObjectEmbedding).count() == 3
