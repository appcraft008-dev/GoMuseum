"""object_embeddings 模型:vec bytes 往返 + (image_id, model) 唯一。"""

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


def test_vec_roundtrip(session):
    s, o, img = session
    vec = np.arange(4, dtype=np.float32)
    s.add(
        ObjectEmbedding(
            object_id=o.id, image_id=img.id, model="dinov2-vits14", vec=vec.tobytes()
        )
    )
    s.commit()
    row = s.query(ObjectEmbedding).one()
    assert np.array_equal(np.frombuffer(row.vec, dtype=np.float32), vec)


def test_unique_image_model(session):
    s, o, img = session
    s.add(ObjectEmbedding(object_id=o.id, image_id=img.id, model="m", vec=b"x"))
    s.commit()
    s.add(ObjectEmbedding(object_id=o.id, image_id=img.id, model="m", vec=b"y"))
    with pytest.raises(Exception):
        s.commit()
