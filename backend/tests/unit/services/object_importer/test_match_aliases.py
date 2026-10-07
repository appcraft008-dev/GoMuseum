"""匹配别名(attributes.match_aliases)是离线一次性生成的,重导入不能冲掉(spec §5)。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    return sessionmaker(bind=engine)()


def test_upsert_preserves_match_aliases():
    s = _session()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    art = {
        "qid": "Q_X",
        "title_en": "L'air du soir",
        "category": "painting",
        "attributes": {"title_i18n": {"fr": "L'Air du soir"}},
    }
    o = upsert_object(s, m.id, dict(art))
    o.attributes = {**o.attributes, "match_aliases": ["The Evening Air"]}
    flag_modified(o, "attributes")
    s.commit()
    upsert_object(s, m.id, dict(art))  # 重导入:attributes 整块覆盖
    s.commit()
    attrs = s.query(MuseumObject).filter_by(qid="Q_X").one().attributes
    assert attrs["match_aliases"] == ["The Evening Air"]
    assert attrs["title_i18n"] == {"fr": "L'Air du soir"}
