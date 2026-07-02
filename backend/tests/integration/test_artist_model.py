from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist


def test_artist_roundtrip():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[Artist.__table__])
    s = sessionmaker(bind=engine)()
    s.add(
        Artist(
            qid="Q296",
            name_zh="梵高",
            name_en="Van Gogh",
            birth="1853",
            death="1890",
            nationality="Netherlands",
            notable_works=["Starry Night"],
            bio={"zh": "梵高生平", "en": "bio"},
        )
    )
    s.commit()
    s.expire_all()
    a = s.query(Artist).filter_by(qid="Q296").one()
    assert (
        a.name_zh == "梵高"
        and a.bio["zh"] == "梵高生平"
        and a.notable_works == ["Starry Night"]
    )
