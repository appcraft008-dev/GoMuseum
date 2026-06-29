from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


def test_evidence_pack_column_roundtrip():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o = upsert_object(s, m.id, {"qid": "Q1", "title_en": "X"})
    o.evidence_pack = {"facts": [{"claim": "c", "value": "v"}]}
    s.commit()
    s.expire_all()  # 清缓存,强制从 DB 列重读(真正守护持久化,而非 identity-map 缓存)
    assert (
        s.query(MuseumObject)
        .filter_by(qid="Q1")
        .one()
        .evidence_pack["facts"][0]["value"]
        == "v"
    )
