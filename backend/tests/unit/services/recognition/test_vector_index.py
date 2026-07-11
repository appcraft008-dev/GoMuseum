"""向量索引服务:全局矩阵点积 + 同qid取max降序 + 馆掩码过滤 + TTL缓存。"""

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
from app.services.recognition import vector_index
from app.services.recognition.embedder import MODEL_NAME


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture()
def session():
    vector_index.invalidate()
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
    yield s
    s.close()
    vector_index.invalidate()


def _add_embedding(s, object_id, image_id, vec):
    s.add(
        ObjectEmbedding(
            object_id=object_id,
            image_id=image_id,
            model=MODEL_NAME,
            vec=_unit(vec).tobytes(),
        )
    )


def _add_object(s, museum_id, qid, title, urls, vecs):
    o = upsert_object(s, museum_id, {"qid": qid, "title_en": title})
    for i, (url, vec) in enumerate(zip(urls, vecs)):
        img = ObjectImage(object_id=o.id, source_url=url, sort=i)
        s.add(img)
        s.flush()
        _add_embedding(s, o.id, img.id, vec)
    return o


def test_same_qid_max_descending(session):
    s = session
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    # Q1 有两张图:一张对齐查询(dot=1.0),一张正交(dot=0.0) → 取 max
    _add_object(s, m.id, "Q1", "A", ["u1", "u2"], [[1, 0, 0, 0], [0, 1, 0, 0]])
    _add_object(s, m.id, "Q2", "B", ["u3"], [[0.6, 0.8, 0, 0]])
    s.commit()

    ranked = vector_index.query_index(s, _unit([1, 0, 0, 0]))
    assert [q for q, _ in ranked] == ["Q1", "Q2"]
    assert ranked[0][1] == pytest.approx(1.0)
    assert ranked[1][1] == pytest.approx(0.6)


def test_museum_filter(session):
    s = session
    orsay = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    louvre = upsert_museum(s, {"slug": "louvre", "name_en": "Louvre"})
    _add_object(s, orsay.id, "Q1", "A", ["u1"], [[1, 0, 0, 0]])
    _add_object(s, louvre.id, "Q2", "B", ["u2"], [[1, 0, 0, 0]])
    s.commit()

    ranked = vector_index.query_index(s, _unit([1, 0, 0, 0]), museum_id=orsay.id)
    assert [q for q, _ in ranked] == ["Q1"]


def test_empty_table(session):
    s = session
    assert vector_index.query_index(s, _unit([1, 0, 0, 0])) == []


def test_cache_ttl_and_invalidate(session):
    s = session
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    _add_object(s, m.id, "Q1", "A", ["u1"], [[1, 0, 0, 0]])
    s.commit()

    assert [q for q, _ in vector_index.query_index(s, _unit([1, 0, 0, 0]))] == ["Q1"]

    _add_object(s, m.id, "Q2", "B", ["u2"], [[1, 0, 0, 0]])
    s.commit()
    # 未 invalidate → 仍走缓存,新行不可见
    assert [q for q, _ in vector_index.query_index(s, _unit([1, 0, 0, 0]))] == ["Q1"]

    vector_index.invalidate()
    got = {q for q, _ in vector_index.query_index(s, _unit([1, 0, 0, 0]))}
    assert got == {"Q1", "Q2"}
